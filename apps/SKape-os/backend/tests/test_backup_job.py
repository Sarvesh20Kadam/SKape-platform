"""Offline checks for the local backup foundation.

These tests do not connect to PostgreSQL, upload a dump, or delete a
retained copy.
"""

import hashlib
import os
import stat
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import backup.publish as publish_module

from app.schema_revision import expected_schema_revisions
from backup.commands import (
    dump_argv,
    postgres_child_environment,
    require_pgpassfile,
    restore_argv,
    restrict_password_file,
)
from backup.dump import require_dump_checksum, validate_dump_file
from backup.errors import BackupError
from backup.manifest import (
    BackupManifest,
    parse_manifest,
    serialize_manifest,
    validate_manifest,
)
from backup.publish import (
    acquire_publication_lock,
    publish_verified_latest,
    release_publication_lock,
)
from backup.retention import (
    MINIMUM_VERIFIED_COPIES,
    ClassifiedBackup,
    copies_authorized_for_deletion,
)
from backup.stale import check_stale


HEADS = expected_schema_revisions()
DIGEST = "a" * 64
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def _payload(**overrides):
    payload = {
        "backup_id": "backup-20261011T120000Z",
        "completed_at": "2026-10-11T12:00:00Z",
        "postgres_major": 16,
        "size_bytes": 11,
        "sha256": DIGEST,
        "schema_revisions": sorted(HEADS),
        "verification_status": "verified",
    }
    payload.update(overrides)
    return payload


def _manifest(**overrides):
    payload = _payload(**overrides)
    completed = datetime.fromisoformat(
        payload["completed_at"].replace("Z", "+00:00")
    )
    return validate_manifest(
        payload,
        expected_revisions=HEADS,
        now=completed,
    )


def _dump(directory, content=b"PGDMPsample"):
    path = directory / "backup.dump"
    path.write_bytes(content)
    return path


def _digest(content):
    return hashlib.sha256(content).hexdigest()


def _classified(
    backup_id,
    backup_class,
    completed_at,
    *,
    verified=True,
    source_backup_id=None,
):
    manifest = _manifest(
        backup_id=backup_id,
        completed_at=completed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        verification_status="verified" if verified else "pending",
    )
    return ClassifiedBackup(
        manifest,
        backup_class,
        source_backup_id=source_backup_id,
    )


def _series(backup_class, count, *, start):
    return [
        _classified(
            f"{backup_class}-{index:02d}",
            backup_class,
            start + timedelta(hours=index),
        )
        for index in range(count)
    ]


def test_backup_package_does_not_reference_the_api_database():
    root = Path(__file__).resolve().parents[1] / "backup"
    sources = [path.read_text(encoding="utf-8") for path in root.glob("*.py")]
    combined = "\n".join(sources)
    assert "app.database" not in combined
    assert "app.main" not in combined


def test_direct_manifest_construction_is_rejected():
    with pytest.raises(BackupError, match="backup manifest is invalid"):
        BackupManifest(
            "backup-20261011T120000Z",
            NOW,
            16,
            11,
            DIGEST,
            tuple(sorted(HEADS)),
            "verified",
        )


def test_validated_manifest_mutation_is_rejected():
    manifest = _manifest(verification_status="pending")
    fields = {
        "backup_id": "other-backup",
        "completed_at": NOW,
        "postgres_major": 15,
        "size_bytes": 12,
        "sha256": "b" * 64,
        "schema_revisions": ("not-a-head",),
        "verification_status": "verified",
    }
    for name, value in fields.items():
        with pytest.raises(BackupError, match="backup manifest is invalid"):
            setattr(manifest, name, value)
        with pytest.raises(BackupError, match="backup manifest is invalid"):
            delattr(manifest, name)
    with pytest.raises(BackupError, match="backup manifest is invalid"):
        object.__setattr__(manifest, "verification_status", "verified")
    assert manifest.verification_status == "pending"
    assert manifest.schema_revisions == tuple(sorted(HEADS))
    assert manifest.verified is False
    restored = parse_manifest(
        serialize_manifest(manifest),
        expected_revisions=HEADS,
        now=NOW,
    )
    assert restored.verification_status == "pending"
    assert restored.schema_revisions == tuple(sorted(HEADS))
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    entries = list(_series("daily", MINIMUM_VERIFIED_COPIES["daily"], start=start))
    pending = _classified(
        "daily-pending",
        "daily",
        start + timedelta(days=2),
        verified=False,
    )
    with pytest.raises(BackupError, match="backup manifest is invalid"):
        object.__setattr__(pending.manifest, "verification_status", "verified")
    assert pending.manifest.verified is False
    assert copies_authorized_for_deletion([*entries, pending]) == []


def test_manifest_round_trip_uses_repository_heads():
    manifest = _manifest()
    parsed = parse_manifest(
        serialize_manifest(manifest),
        expected_revisions=HEADS,
        now=NOW,
    )
    assert parsed.backup_id == manifest.backup_id
    assert parsed.schema_revisions == tuple(sorted(HEADS))
    assert parsed.postgres_major == 16
    assert parsed.verified


@pytest.mark.parametrize(
    "overrides",
    [
        {"backup_id": "../latest"},
        {"completed_at": "2026-10-11 12:00:00"},
        {"size_bytes": 0},
        {"size_bytes": True},
        {"sha256": "A" * 64},
        {"schema_revisions": []},
        {"verification_status": "published"},
        {"extra": "field"},
    ],
)
def test_malformed_manifest_is_rejected(overrides):
    payload = _payload(**overrides)
    if "extra" not in overrides:
        payload.pop("extra", None)
    with pytest.raises(BackupError, match="backup manifest is invalid"):
        validate_manifest(payload, expected_revisions=HEADS, now=NOW)


def test_schema_mismatch_does_not_echo_revision_ids():
    payload = _payload(schema_revisions=["not-a-head"])
    with pytest.raises(BackupError, match="schema revision does not match") as caught:
        validate_manifest(payload, expected_revisions=HEADS, now=NOW)
    assert "not-a-head" not in str(caught.value)
    assert "f6b1c0a84e22" not in str(caught.value)


def test_postgres_major_other_than_16_is_rejected():
    with pytest.raises(BackupError, match="PostgreSQL major version is not 16"):
        validate_manifest(
            _payload(postgres_major=15),
            expected_revisions=HEADS,
            now=NOW,
        )


def test_custom_format_dump_records_size_and_sha256(tmp_path):
    content = b"PGDMPsample"
    path = _dump(tmp_path, content)
    info = validate_dump_file(path)
    assert info.size == len(content)
    assert info.sha256 == _digest(content)
    require_dump_checksum(path, size=info.size, digest=info.sha256)


def test_empty_dump_is_rejected(tmp_path):
    path = _dump(tmp_path, b"")
    with pytest.raises(BackupError, match="empty backup"):
        validate_dump_file(path)


def test_dump_without_custom_format_marker_is_rejected(tmp_path):
    path = _dump(tmp_path, b"not-a-dump")
    with pytest.raises(BackupError, match="custom-format"):
        validate_dump_file(path)


def test_checksum_mismatch_is_rejected(tmp_path):
    path = _dump(tmp_path, b"PGDMPsample")
    with pytest.raises(BackupError, match="backup checksum does not match"):
        require_dump_checksum(path, size=11, digest="b" * 64)


def test_size_mismatch_is_rejected(tmp_path):
    content = b"PGDMPsample"
    path = _dump(tmp_path, content)
    with pytest.raises(BackupError, match="backup checksum does not match"):
        require_dump_checksum(path, size=len(content) - 1, digest=_digest(content))


def test_invalid_calendar_date_is_rejected():
    with pytest.raises(BackupError, match="backup manifest is invalid"):
        validate_manifest(
            _payload(completed_at="2026-02-31T00:00:00Z"),
            expected_revisions=HEADS,
            now=NOW,
        )


def test_future_manifest_timestamp_is_rejected():
    with pytest.raises(BackupError, match="backup completion time is invalid"):
        validate_manifest(
            _payload(completed_at="2026-10-11T12:00:01Z"),
            expected_revisions=HEADS,
            now=NOW,
        )


def test_symlink_dump_is_rejected(tmp_path, monkeypatch):
    path = _dump(tmp_path, b"PGDMPsample")
    monkeypatch.setattr(Path, "is_symlink", lambda self: self == path)
    with pytest.raises(BackupError, match="custom-format"):
        validate_dump_file(path)


def test_dump_command_omits_password_and_database_url():
    password = "db-password"
    url = "postgresql://backup_reader:db-password@db.internal:5432/skape"
    argv = dump_argv(
        "pg_dump",
        host="db.internal",
        port=5432,
        user="backup_reader",
        database="skape",
    )
    rendered = " ".join(argv)
    assert password not in rendered
    assert url not in rendered
    assert "://" not in rendered
    assert argv[1:4] == ["-Fc", "--no-owner", "--no-acl"]
    assert "-d" in argv and "skape" in argv


def test_restore_command_omits_clean_password_and_url():
    argv = restore_argv(
        r"C:\PostgreSQL\16\bin\pg_restore.exe",
        host="db.internal",
        port=5432,
        user="backup_reader",
        database="skape_restore",
    )
    rendered = " ".join(argv)
    assert "--clean" not in argv
    assert "--single-transaction" in argv
    assert "://" not in rendered
    assert argv[0].endswith("pg_restore.exe")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"host": "postgresql://db.internal", "port": 5432, "user": "reader", "database": "skape"},
        {"host": "db.internal", "port": 5432, "user": "reader", "database": "skape/prod"},
        {"host": "db.internal", "port": 0, "user": "reader", "database": "skape"},
        {"host": "db.internal", "port": True, "user": "reader", "database": "skape"},
    ],
)
def test_unsafe_connection_values_are_rejected(kwargs):
    with pytest.raises(BackupError, match="PostgreSQL command is not safe"):
        dump_argv("pg_dump", **kwargs)


def test_unexpected_tool_is_rejected():
    with pytest.raises(BackupError, match="PostgreSQL command is not safe"):
        dump_argv("pg_restore", host="db.internal", port=5432, user="reader", database="skape")


@pytest.mark.parametrize(
    "executable",
    ["bin/pg_dump", "../pg_dump", r".\pg_dump", "pg_dump.bat"],
)
def test_relative_or_ambiguous_executable_is_rejected(executable):
    with pytest.raises(BackupError, match="PostgreSQL command is not safe"):
        dump_argv(
            executable,
            host="db.internal",
            port=5432,
            user="reader",
            database="skape",
        )


def test_password_file_is_removed_when_unix_mode_does_not_stick(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "pgpass"
    path.write_text("hidden\n", encoding="utf-8")
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(os, "chmod", lambda target, mode: None)
    with pytest.raises(
        BackupError,
        match="permissions could not be restricted",
    ):
        restrict_password_file(path)
    assert not path.exists()
    assert list(tmp_path.iterdir()) == []


def test_child_environment_drops_secrets_and_database_urls(tmp_path):
    password_file = tmp_path / "pgpass"
    password_file.write_text("unused\n", encoding="utf-8")
    environment = postgres_child_environment(
        {
            "PATH": r"C:\PostgreSQL\16\bin",
            "PGPASSWORD": "db-password",
            "PGHOST": "db.internal",
            "DATABASE_URL": "postgresql://reader:db-password@db.internal/skape",
            "SKAPE_TEST_DATABASE_URL": "postgresql://reader:db-password@db.internal/admin",
            "AWS_SECRET_ACCESS_KEY": "storage-secret",
            "R2_TOKEN": "storage-token",
            "AUTHORIZATION": "Bearer auth-value",
            "HTTP_AUTHORIZATION": "Bearer auth-value",
        },
        pgpassfile=str(password_file),
    )
    rendered = " ".join(environment.values())
    assert environment["PATH"] == r"C:\PostgreSQL\16\bin"
    assert environment["PGPASSFILE"] == os.path.normpath(str(password_file))
    assert "PGPASSWORD" not in environment
    assert "DATABASE_URL" not in environment
    assert "PGHOST" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "R2_TOKEN" not in environment
    assert "AUTHORIZATION" not in environment
    assert "HTTP_AUTHORIZATION" not in environment
    assert "db-password" not in rendered
    assert "postgresql://" not in rendered
    assert "storage-secret" not in rendered
    assert "auth-value" not in rendered


@pytest.mark.parametrize(
    "candidate",
    ["pgpass", "../pgpass", r"..\pgpass", "C:pgpass"],
)
def test_pgpassfile_rejects_relative_paths(candidate):
    with pytest.raises(BackupError, match="password file is not safe"):
        require_pgpassfile(candidate)


def test_pgpassfile_rejects_parent_traversal(tmp_path):
    present = tmp_path / "pgpass"
    present.write_text("unused\n", encoding="utf-8")
    candidates = (
        str(tmp_path / ".." / "pgpass"),
        str(tmp_path / "nested" / ".." / "pgpass"),
        os.path.normpath(str(present)) + os.sep + "..",
    )
    for candidate in candidates:
        with pytest.raises(BackupError, match="password file is not safe"):
            postgres_child_environment(
                {"PATH": r"C:\PostgreSQL\16\bin"},
                pgpassfile=candidate,
            )


def test_pgpassfile_rejects_a_missing_file_and_a_directory(tmp_path):
    with pytest.raises(BackupError, match="password file is not safe"):
        require_pgpassfile(str(tmp_path / "missing"))
    with pytest.raises(BackupError, match="password file is not safe"):
        require_pgpassfile(str(tmp_path))


def test_pgpassfile_rejects_a_symlink(tmp_path, monkeypatch):
    target = tmp_path / "pgpass"
    target.write_text("unused\n", encoding="utf-8")
    monkeypatch.setattr(Path, "is_symlink", lambda self: Path(self) == target)
    with pytest.raises(BackupError, match="password file is not safe"):
        require_pgpassfile(str(target))


def test_pgpassfile_rejects_an_lstat_symlink(tmp_path, monkeypatch):
    target = tmp_path / "pgpass"
    target.write_text("unused\n", encoding="utf-8")
    monkeypatch.setattr(Path, "is_symlink", lambda self: False)

    class Info:
        st_mode = stat.S_IFLNK | 0o777

    monkeypatch.setattr(os, "lstat", lambda path: Info())
    with pytest.raises(BackupError, match="password file is not safe"):
        require_pgpassfile(str(target))


def test_pgpassfile_rejects_insecure_posix_permissions(tmp_path, monkeypatch):
    target = tmp_path / "pgpass"
    target.write_text("unused\n", encoding="utf-8")
    monkeypatch.setattr("backup.commands._platform_name", lambda: "posix")
    monkeypatch.setattr(Path, "is_symlink", lambda self: False)

    class Info:
        st_mode = stat.S_IFREG | 0o644

    monkeypatch.setattr(os, "lstat", lambda path: Info())
    with pytest.raises(BackupError, match="password file is not safe"):
        require_pgpassfile(str(target))


def test_pgpassfile_accepts_posix_owner_only_mode_when_status_says_so(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "pgpass"
    target.write_text("unused\n", encoding="utf-8")
    monkeypatch.setattr("backup.commands._platform_name", lambda: "posix")
    monkeypatch.setattr(Path, "is_symlink", lambda self: False)

    class Info:
        st_mode = stat.S_IFREG | 0o600

    monkeypatch.setattr(os, "lstat", lambda path: Info())
    assert require_pgpassfile(str(target)) == os.path.normpath(str(target))


def test_retention_deletes_only_the_oldest_copy_above_each_minimum():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    entries = (
        _series("daily", 15, start=start)
        + _series("weekly", 9, start=start)
        + _series("monthly", 7, start=start)
    )
    authorized = copies_authorized_for_deletion(entries)
    assert [(item.backup_class, item.manifest.backup_id) for item in authorized] == [
        ("daily", "daily-00"),
        ("weekly", "weekly-00"),
        ("monthly", "monthly-00"),
    ]
    assert all(
        item.manifest.backup_id != "daily-14" for item in authorized
    )


@pytest.mark.parametrize(
    ("backup_class", "count"),
    [
        ("daily", MINIMUM_VERIFIED_COPIES["daily"]),
        ("weekly", MINIMUM_VERIFIED_COPIES["weekly"]),
        ("monthly", MINIMUM_VERIFIED_COPIES["monthly"]),
        ("daily", MINIMUM_VERIFIED_COPIES["daily"] - 1),
        ("weekly", MINIMUM_VERIFIED_COPIES["weekly"] - 1),
        ("monthly", MINIMUM_VERIFIED_COPIES["monthly"] - 1),
    ],
)
def test_retention_keeps_a_class_at_or_below_its_minimum(backup_class, count):
    entries = _series(
        backup_class,
        count,
        start=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    assert copies_authorized_for_deletion(entries) == []


def test_retention_keeps_every_copy_that_shares_the_newest_time():
    moment = datetime(2026, 10, 11, tzinfo=timezone.utc)
    entries = [
        _classified(f"daily-{index:02d}", "daily", moment)
        for index in range(15)
    ]
    assert copies_authorized_for_deletion(entries) == []


def test_retention_does_not_delete_the_newest_verified_backup():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    entries = _series("daily", 15, start=start)
    entries.append(
        _classified(
            "monthly-new",
            "monthly",
            start + timedelta(days=40),
        )
    )
    authorized = copies_authorized_for_deletion(entries)
    assert "monthly-new" not in [
        item.manifest.backup_id for item in authorized
    ]
    assert [item.manifest.backup_id for item in authorized] == ["daily-00"]


def test_unverified_copies_are_not_deletion_candidates():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    entries = _series("daily", 14, start=start)
    entries.append(
        _classified(
            "daily-pending",
            "daily",
            start - timedelta(days=1),
            verified=False,
        )
    )
    assert copies_authorized_for_deletion(entries) == []


def test_duplicate_retained_backup_authorizes_nothing():
    entry = _classified(
        "daily-00",
        "daily",
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(BackupError, match="duplicate retained backup"):
        copies_authorized_for_deletion([entry, entry])


def test_stale_boundary_is_older_than_24_hours():
    fresh = check_stale(
        _payload(completed_at="2026-10-10T12:00:00Z"),
        expected_revisions=HEADS,
        now=NOW,
    )
    assert fresh.status == "fresh"
    stale = check_stale(
        _payload(completed_at="2026-10-10T11:59:59Z"),
        expected_revisions=HEADS,
        now=NOW,
    )
    assert stale.stale


def test_unverified_or_future_metadata_is_rejected():
    with pytest.raises(BackupError, match="backup is not verified"):
        check_stale(
            _payload(verification_status="pending"),
            expected_revisions=HEADS,
            now=NOW,
        )
    with pytest.raises(BackupError, match="backup completion time is invalid"):
        check_stale(
            _payload(completed_at="2026-10-11T12:00:01Z"),
            expected_revisions=HEADS,
            now=NOW,
        )


def _backup_directory(tmp_path, *, placeholder=True):
    directory = tmp_path / "skape-backup-unit"
    directory.mkdir()
    latest = directory / "latest.json"
    if placeholder:
        latest.write_text('{"preserved":true}\n', encoding="utf-8")
    return directory, latest


def _publish(directory, dump, **overrides):
    payload = _payload(
        sha256=_digest(b"PGDMPsample"),
        size_bytes=len(b"PGDMPsample"),
        **overrides,
    )
    completed = datetime.fromisoformat(
        payload["completed_at"].replace("Z", "+00:00")
    )
    return publish_verified_latest(
        directory,
        payload,
        dump,
        expected_revisions=HEADS,
        now=max(completed, NOW),
    )


def test_failed_publication_preserves_latest(tmp_path):
    directory, latest = _backup_directory(tmp_path)
    content = b"PGDMPsample"
    dump = _dump(directory, content)
    original = latest.read_text(encoding="utf-8")
    cases = [
        _payload(sha256="b" * 64, size_bytes=len(content)),
        _payload(
            sha256=_digest(content),
            size_bytes=len(content),
            verification_status="pending",
        ),
        _payload(
            sha256=_digest(content),
            size_bytes=len(content),
            schema_revisions=["not-a-head"],
        ),
    ]
    for payload in cases:
        with pytest.raises(BackupError):
            publish_verified_latest(
                directory,
                payload,
                dump,
                expected_revisions=HEADS,
                now=NOW,
            )
        assert latest.read_text(encoding="utf-8") == original
        assert not _temporary_manifests(directory)


def test_verified_publication_replaces_an_older_latest(tmp_path):
    directory, latest = _backup_directory(tmp_path, placeholder=False)
    dump = _dump(directory)
    _publish(directory, dump, completed_at="2026-10-11T11:00:00Z", backup_id="backup-old")
    _publish(directory, dump, completed_at="2026-10-11T12:00:00Z", backup_id="backup-new")
    published = parse_manifest(
        latest.read_text(encoding="utf-8"),
        expected_revisions=HEADS,
        now=NOW,
    )
    assert published.backup_id == "backup-new"
    assert published.verified
    names = set(os.listdir(directory))
    assert {"backup.dump", "latest.json", ".publish.lock"} <= names
    assert not _temporary_manifests(directory)


def test_older_publication_preserves_latest(tmp_path):
    directory, latest = _backup_directory(tmp_path, placeholder=False)
    dump = _dump(directory)
    _publish(directory, dump)
    original = latest.read_text(encoding="utf-8")
    with pytest.raises(BackupError, match="refusing to publish an older backup"):
        _publish(
            directory,
            dump,
            backup_id="backup-old",
            completed_at="2026-10-11T11:00:00Z",
        )
    assert latest.read_text(encoding="utf-8") == original
    assert not _temporary_manifests(directory)


def test_equal_timestamp_keeps_a_different_backup(tmp_path):
    directory, latest = _backup_directory(tmp_path, placeholder=False)
    dump = _dump(directory)
    _publish(directory, dump, backup_id="backup-a")
    original = latest.read_text(encoding="utf-8")
    with pytest.raises(BackupError, match="refusing to replace the verified backup"):
        _publish(directory, dump, backup_id="backup-b")
    assert latest.read_text(encoding="utf-8") == original


def test_equal_timestamp_accepts_the_same_manifest(tmp_path):
    directory, latest = _backup_directory(tmp_path, placeholder=False)
    dump = _dump(directory)
    _publish(directory, dump)
    original = latest.read_text(encoding="utf-8")
    published = _publish(directory, dump)
    assert published.backup_id == "backup-20261011T120000Z"
    assert latest.read_text(encoding="utf-8") == original


def test_symlink_latest_pointer_is_rejected(tmp_path, monkeypatch):
    directory, latest = _backup_directory(tmp_path)
    original = latest.read_text(encoding="utf-8")
    dump = _dump(directory)
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "latest.json")
    with pytest.raises(BackupError, match="refusing to publish through a symlink"):
        _publish(directory, dump, backup_id="backup-new")
    assert latest.read_text(encoding="utf-8") == original
    assert not _temporary_manifests(directory)


def test_invalid_latest_pointer_is_preserved(tmp_path):
    directory, latest = _backup_directory(tmp_path)
    original = latest.read_text(encoding="utf-8")
    dump = _dump(directory)
    with pytest.raises(BackupError, match="unverified backup pointer"):
        _publish(directory, dump)
    assert latest.read_text(encoding="utf-8") == original
    assert not _temporary_manifests(directory)


def test_interrupted_publication_preserves_latest(tmp_path, monkeypatch):
    directory, latest = _backup_directory(tmp_path, placeholder=False)
    dump = _dump(directory)
    _publish(directory, dump, completed_at="2026-10-11T11:00:00Z", backup_id="backup-old")
    original = latest.read_text(encoding="utf-8")

    def fail_replace(source, target):
        raise OSError("interrupted")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(BackupError, match="backup publication failed"):
        _publish(directory, dump, backup_id="backup-new")
    assert latest.read_text(encoding="utf-8") == original
    assert not _temporary_manifests(directory)


def test_locked_publication_fails_closed(tmp_path, monkeypatch):
    directory, latest = _backup_directory(tmp_path, placeholder=False)
    dump = _dump(directory)
    _publish(directory, dump, completed_at="2026-10-11T11:00:00Z", backup_id="backup-old")
    original = latest.read_text(encoding="utf-8")
    monkeypatch.setattr(publish_module, "LOCK_WAIT_SECONDS", 0.2)
    held = acquire_publication_lock(directory)
    try:
        with pytest.raises(BackupError, match="already in progress"):
            _publish(directory, dump, backup_id="backup-new")
    finally:
        release_publication_lock(held)
    assert latest.read_text(encoding="utf-8") == original
    assert not _temporary_manifests(directory)


def test_overlapping_publication_keeps_the_newer_manifest(tmp_path, monkeypatch):
    directory, latest = _backup_directory(tmp_path, placeholder=False)
    dump = _dump(directory)
    _publish(directory, dump, completed_at="2026-10-11T10:00:00Z", backup_id="backup-base")
    started = threading.Event()
    waiting = threading.Event()
    release = threading.Event()
    original_replace = os.replace
    original_sleep = time.sleep
    calls = {"count": 0}

    def slow_replace(source, target):
        calls["count"] += 1
        if calls["count"] == 1:
            started.set()
            assert waiting.wait(5)
            assert release.wait(5)
        original_replace(source, target)

    def slow_sleep(seconds):
        waiting.set()
        original_sleep(seconds)

    monkeypatch.setattr(os, "replace", slow_replace)
    monkeypatch.setattr(publish_module.time, "sleep", slow_sleep)
    errors = []

    def publish(backup_id, completed_at):
        try:
            _publish(
                directory,
                dump,
                backup_id=backup_id,
                completed_at=completed_at,
            )
        except BackupError as exc:
            errors.append(str(exc))

    newer = threading.Thread(
        target=publish,
        args=("backup-new", "2026-10-11T12:00:00Z"),
    )
    older = threading.Thread(
        target=publish,
        args=("backup-old", "2026-10-11T11:00:00Z"),
    )
    newer.start()
    older.start()
    assert started.wait(5)
    assert waiting.wait(5)
    release.set()
    newer.join(5)
    older.join(5)
    assert not newer.is_alive()
    assert not older.is_alive()
    published = parse_manifest(
        latest.read_text(encoding="utf-8"),
        expected_revisions=HEADS,
        now=NOW,
    )
    assert published.backup_id == "backup-new"
    assert errors == [] or errors == ["refusing to publish an older backup"]
    assert not _temporary_manifests(directory)


def test_lock_open_rejects_a_different_file_identity(tmp_path, monkeypatch):
    directory, latest = _backup_directory(tmp_path, placeholder=False)
    dump = _dump(directory)
    _publish(
        directory,
        dump,
        completed_at="2026-10-11T11:00:00Z",
        backup_id="backup-old",
    )
    original = latest.read_text(encoding="utf-8")
    real_fstat = os.fstat

    def mismatch(fd):
        stat = real_fstat(fd)
        return type("Stat", (), {"st_dev": stat.st_dev, "st_ino": stat.st_ino + 1})()

    monkeypatch.setattr(os, "fstat", mismatch)
    with pytest.raises(BackupError, match="refusing to publish"):
        _publish(directory, dump, backup_id="backup-new")
    assert latest.read_text(encoding="utf-8") == original


def test_publication_refuses_an_unprefixed_directory(tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    latest = directory / "latest.json"
    latest.write_text("keep\n", encoding="utf-8")
    with pytest.raises(BackupError, match="refusing to publish"):
        publish_verified_latest(
            directory,
            _payload(),
            _dump(directory),
            expected_revisions=HEADS,
            now=NOW,
        )
    assert latest.read_text(encoding="utf-8") == "keep\n"


def _temporary_manifests(directory):
    return [
        path.name
        for path in directory.iterdir()
        if path.name.startswith(".latest-")
    ]


def test_shared_backup_id_does_not_authorize_the_daily_object():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    entries = _series("daily", 15, start=start)
    entries.append(_classified("daily-00", "weekly", start + timedelta(days=7)))
    authorized = copies_authorized_for_deletion(entries)
    assert ("daily", "daily-00") not in [
        (item.backup_class, item.manifest.backup_id) for item in authorized
    ]
    assert "logical/daily/daily-00.dump" not in [
        item.object_key for item in authorized
    ]
    assert entries[-1].object_key == "logical/weekly/daily-00.dump"


def test_referenced_daily_object_is_not_deleted():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    entries = _series("daily", 16, start=start)
    entries.append(
        _classified(
            "weekly-kept",
            "weekly",
            start + timedelta(days=7),
            source_backup_id="daily-00",
        )
    )
    authorized = copies_authorized_for_deletion(entries)
    identities = [
        (item.backup_class, item.manifest.backup_id) for item in authorized
    ]
    assert ("daily", "daily-00") not in identities
    assert identities == [("daily", "daily-01")]


def test_shared_physical_object_is_rejected():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    daily = _classified("daily-00", "daily", start)
    weekly = ClassifiedBackup(
        _manifest(backup_id="weekly-00", completed_at="2026-10-08T00:00:00Z"),
        "weekly",
        physical_object_key=daily.object_key,
    )
    with pytest.raises(BackupError, match="backup object key conflicts"):
        copies_authorized_for_deletion([daily, weekly])


def test_conflicting_object_key_is_rejected():
    manifest = _manifest(
        backup_id="daily-00",
        completed_at="2026-10-01T00:00:00Z",
    )
    with pytest.raises(BackupError, match="backup object key conflicts"):
        ClassifiedBackup(
            manifest,
            "daily",
            object_key="logical/weekly/daily-00.dump",
        )


def test_missing_manifest_is_rejected():
    with pytest.raises(BackupError, match="backup manifest is missing"):
        ClassifiedBackup(None, "daily")


def test_ambiguous_daily_reference_is_rejected():
    weekly = _classified(
        "weekly-00",
        "weekly",
        datetime(2026, 10, 8, tzinfo=timezone.utc),
        source_backup_id="missing-daily",
    )
    with pytest.raises(BackupError, match="backup reference is ambiguous"):
        copies_authorized_for_deletion([weekly])
