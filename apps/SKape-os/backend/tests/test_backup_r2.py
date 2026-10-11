"""Offline checks for the R2 backup adapter.

The object store is in memory. These tests do not contact Cloudflare,
open a network connection, or run pg_dump.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.schema_revision import expected_schema_revisions
from backup.errors import BackupError
from backup.manifest import serialize_manifest, validate_manifest
from backup.r2 import (
    LATEST_KEY,
    ObjectInfo,
    StorePreconditionError,
    publish_remote_backup,
)


HEADS = expected_schema_revisions()
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
DUMP = b"PGDMPsample"
DIGEST = hashlib.sha256(DUMP).hexdigest()
SECRET = "synthetic-secret-value"
URL = "https://bucket.example/object?X-Amz-Signature=synthetic-secret-value"


class MemoryStore:
    """Conditional object store with stable ETags and no delete method."""

    def __init__(self):
        self._objects = {}
        self._sequence = 0
        self.attempts = []
        self._corrupt = set()
        self._race = None

    def seed(self, key, body):
        self._sequence += 1
        self._objects[key] = {
            "body": bytes(body),
            "etag": "etag-%d" % self._sequence,
        }

    def corrupt(self, key):
        self._corrupt.add(key)

    def lose_next_put(self, key, winner):
        self._race = (key, bytes(winner))

    def _visible(self, key, item):
        if key in self._corrupt:
            return b"PGDMPcorrupt"
        return item["body"]

    def head(self, key):
        item = self._objects.get(key)
        if item is None:
            return None
        body = self._visible(key, item)
        return ObjectInfo(len(body), item["etag"])

    def get(self, key):
        item = self._objects.get(key)
        if item is None:
            raise BackupError("backup publication failed")
        body = self._visible(key, item)
        return body, ObjectInfo(len(body), item["etag"])

    def put(self, key, body, *, if_match=None, if_none_match=None):
        self.attempts.append(
            {
                "key": key,
                "if_match": if_match,
                "if_none_match": if_none_match,
            }
        )
        if self._race is not None and self._race[0] == key:
            winner = self._race[1]
            self._race = None
            self._sequence += 1
            self._objects[key] = {
                "body": winner,
                "etag": "etag-%d" % self._sequence,
            }
            raise StorePreconditionError(
                "backup publication precondition failed"
            )
        if (if_match is None) == (if_none_match is None):
            raise BackupError("backup publication failed")
        current = self._objects.get(key)
        if if_none_match is not None:
            if if_none_match != "*" or current is not None:
                raise StorePreconditionError(
                    "backup publication precondition failed"
                )
        elif current is None or current["etag"] != if_match:
            raise StorePreconditionError(
                "backup publication precondition failed"
            )
        self._sequence += 1
        self._objects[key] = {
            "body": bytes(body),
            "etag": "etag-%d" % self._sequence,
        }
        return ObjectInfo(len(body), self._objects[key]["etag"])


def _payload(**overrides):
    payload = {
        "backup_id": "backup-20261011T120000Z",
        "completed_at": "2026-10-11T12:00:00Z",
        "postgres_major": 16,
        "size_bytes": len(DUMP),
        "sha256": DIGEST,
        "schema_revisions": sorted(HEADS),
        "verification_status": "verified",
    }
    payload.update(overrides)
    return payload


def _dump_file(directory, content=DUMP):
    path = directory / "backup.dump"
    path.write_bytes(content)
    return path


def _publish(store, directory, **overrides):
    backup_class = overrides.pop("backup_class", "daily")
    payload = _payload(**overrides)
    return publish_remote_backup(
        store,
        backup_class=backup_class,
        dump_path=_dump_file(directory),
        payload=payload,
        expected_revisions=HEADS,
        now=NOW,
    )


def _manifest_key(backup_class, backup_id):
    return "logical/%s/%s.json" % (backup_class, backup_id)


def _dump_key(backup_class, backup_id):
    return "logical/%s/%s.dump" % (backup_class, backup_id)


def test_pending_manifest_is_rejected_before_any_write(tmp_path):
    store = MemoryStore()
    with pytest.raises(BackupError, match="unverified backup"):
        _publish(store, tmp_path, verification_status="pending")
    assert store.attempts == []
    assert store._objects == {}


def test_local_checksum_mismatch_is_rejected_before_any_write(tmp_path):
    store = MemoryStore()
    with pytest.raises(BackupError, match="checksum does not match"):
        _publish(store, tmp_path, sha256="b" * 64)
    assert store.attempts == []


def test_local_read_error_does_not_expose_the_filesystem_path(
    tmp_path,
    monkeypatch,
):
    dump = _dump_file(tmp_path)
    marker = str(dump)

    def fail_read(self):
        raise OSError(13, "Permission denied", marker)

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    store = MemoryStore()
    with pytest.raises(BackupError, match="checksum does not match") as caught:
        publish_remote_backup(
            store,
            backup_class="daily",
            dump_path=dump,
            payload=_payload(),
            expected_revisions=HEADS,
            now=NOW,
        )
    error = caught.value
    assert marker not in str(error)
    assert "Permission denied" not in str(error)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert store.attempts == []


def test_successful_upload_publishes_the_pointer_last(tmp_path):
    store = MemoryStore()
    manifest = _publish(store, tmp_path)
    backup_id = manifest.backup_id
    dump_key = _dump_key("daily", backup_id)
    sidecar = _manifest_key("daily", backup_id)
    assert [item["key"] for item in store.attempts] == [
        dump_key,
        sidecar,
        LATEST_KEY,
    ]
    assert store._objects[dump_key]["body"] == DUMP
    canonical = serialize_manifest(manifest).encode("utf-8")
    assert store._objects[sidecar]["body"] == canonical
    assert store._objects[LATEST_KEY]["body"] == canonical
    assert manifest.verified


def test_repeated_upload_is_idempotent(tmp_path):
    store = MemoryStore()
    first = _publish(store, tmp_path)
    etag = store.head(LATEST_KEY).etag
    attempts = len(store.attempts)
    second = _publish(store, tmp_path)
    assert second.backup_id == first.backup_id
    assert store.head(LATEST_KEY).etag == etag
    assert len(store.attempts) == attempts


def test_existing_identical_dump_is_accepted(tmp_path):
    store = MemoryStore()
    dump_key = _dump_key("daily", "backup-20261011T120000Z")
    store.seed(dump_key, DUMP)
    _publish(store, tmp_path)
    assert dump_key not in [item["key"] for item in store.attempts]
    assert LATEST_KEY in store._objects


def test_conflicting_dump_does_not_change_latest(tmp_path):
    store = MemoryStore()
    dump_key = _dump_key("daily", "backup-20261011T120000Z")
    store.seed(dump_key, b"PGDMP" + SECRET.encode("ascii"))
    original = store._objects[dump_key]["body"]
    with pytest.raises(BackupError, match="checksum does not match") as caught:
        _publish(store, tmp_path)
    assert SECRET not in str(caught.value)
    assert LATEST_KEY not in store._objects
    assert store._objects[dump_key]["body"] == original


def test_corrupted_download_does_not_publish_latest(tmp_path):
    store = MemoryStore()
    dump_key = _dump_key("daily", "backup-20261011T120000Z")
    store.corrupt(dump_key)
    with pytest.raises(BackupError, match="checksum does not match") as caught:
        _publish(store, tmp_path)
    assert SECRET not in str(caught.value)
    assert b"PGDMPcorrupt" not in str(caught.value).encode("utf-8")
    assert LATEST_KEY not in store._objects
    assert _manifest_key("daily", "backup-20261011T120000Z") not in store._objects


def test_conflicting_manifest_sidecar_is_rejected(tmp_path):
    store = MemoryStore()
    backup_id = "backup-20261011T120000Z"
    store.seed(_dump_key("daily", backup_id), DUMP)
    store.seed(_manifest_key("daily", backup_id), b"{}\n")
    with pytest.raises(BackupError, match="manifest conflicts"):
        _publish(store, tmp_path)
    assert LATEST_KEY not in store._objects
    assert store._objects[_manifest_key("daily", backup_id)]["body"] == b"{}\n"


def test_older_manifest_is_refused(tmp_path):
    store = MemoryStore()
    _publish(store, tmp_path)
    latest = store._objects[LATEST_KEY]["body"]
    with pytest.raises(BackupError, match="older backup"):
        _publish(
            store,
            tmp_path,
            backup_id="backup-earlier",
            completed_at="2026-10-11T11:00:00Z",
        )
    assert store._objects[LATEST_KEY]["body"] == latest


def test_different_manifest_with_the_same_timestamp_is_refused(tmp_path):
    store = MemoryStore()
    _publish(store, tmp_path)
    latest = store._objects[LATEST_KEY]["body"]
    with pytest.raises(BackupError, match="replace the verified backup"):
        _publish(store, tmp_path, backup_id="backup-other")
    assert store._objects[LATEST_KEY]["body"] == latest


def test_identical_manifest_is_accepted_without_rewriting_latest(tmp_path):
    store = MemoryStore()
    _publish(store, tmp_path)
    etag = store.head(LATEST_KEY).etag
    _publish(store, tmp_path)
    assert store.head(LATEST_KEY).etag == etag
    assert len(
        [item for item in store.attempts if item["key"] == LATEST_KEY]
    ) == 1


def test_lost_race_preserves_the_winner(tmp_path):
    store = MemoryStore()
    winner = validate_manifest(
        _payload(
            backup_id="backup-winner",
            completed_at="2026-10-11T12:00:00Z",
        ),
        expected_revisions=HEADS,
        now=NOW,
    )
    winner_body = serialize_manifest(winner).encode("utf-8")
    store.lose_next_put(LATEST_KEY, winner_body)
    with pytest.raises(BackupError, match="replace the verified backup") as caught:
        _publish(store, tmp_path)
    assert store._objects[LATEST_KEY]["body"] == winner_body
    latest_attempts = [
        item for item in store.attempts if item["key"] == LATEST_KEY
    ]
    assert len(latest_attempts) == 1
    assert latest_attempts[0]["if_none_match"] == "*"
    assert "etag-" not in str(caught.value)


def test_lost_race_accepts_the_same_canonical_manifest(tmp_path):
    store = MemoryStore()
    manifest = validate_manifest(
        _payload(),
        expected_revisions=HEADS,
        now=NOW,
    )
    canonical = serialize_manifest(manifest).encode("utf-8")
    store.lose_next_put(LATEST_KEY, canonical)
    published = _publish(store, tmp_path)
    assert serialize_manifest(published).encode("utf-8") == canonical
    assert store._objects[LATEST_KEY]["body"] == canonical
    latest_attempts = [
        item for item in store.attempts if item["key"] == LATEST_KEY
    ]
    assert len(latest_attempts) == 1


def test_daily_and_weekly_keys_stay_distinct(tmp_path):
    store = MemoryStore()
    backup_id = "backup-20261011T120000Z"
    _publish(store, tmp_path, backup_class="daily")
    _publish(store, tmp_path, backup_class="weekly")
    daily = _dump_key("daily", backup_id)
    weekly = _dump_key("weekly", backup_id)
    assert daily != weekly
    assert store._objects[daily]["body"] == DUMP
    assert store._objects[weekly]["body"] == DUMP
    assert store._objects[daily] is not store._objects[weekly]


def test_invalid_backup_class_writes_nothing(tmp_path):
    store = MemoryStore()
    with pytest.raises(BackupError, match="backup class is invalid"):
        _publish(store, tmp_path, backup_class="hourly")
    assert store.attempts == []


def test_store_errors_hide_urls_and_secret_text(tmp_path):
    class Exploding:
        def head(self, key):
            raise RuntimeError(URL)

        def get(self, key):
            raise RuntimeError(URL)

        def put(self, key, body, *, if_match=None, if_none_match=None):
            raise RuntimeError(URL)

    with pytest.raises(BackupError, match="publication failed") as caught:
        publish_remote_backup(
            Exploding(),
            backup_class="daily",
            dump_path=_dump_file(tmp_path),
            payload=_payload(),
            expected_revisions=HEADS,
            now=NOW,
        )
    message = str(caught.value)
    assert SECRET not in message
    assert "https://" not in message
    assert "X-Amz-Signature" not in message
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_adapter_has_no_delete_and_does_not_import_runtime_modules():
    source = Path(__file__).resolve().parents[1].joinpath(
        "backup", "r2.py"
    ).read_text(encoding="utf-8")
    assert "app.database" not in source
    assert "app.main" not in source
    assert "backup.runner" not in source
    assert "def delete" not in source
    assert not hasattr(MemoryStore(), "delete")
