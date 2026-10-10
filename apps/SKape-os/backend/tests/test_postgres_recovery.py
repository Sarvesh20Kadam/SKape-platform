"""Logical backup and restore drill for a disposable PostgreSQL database.

The drill runs only when SKAPE_RECOVERY_DRILL=1. It fails if PostgreSQL
is required but the test URL or client tools are missing. It does not
skip in that mode.
"""

import asyncio
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.api.health import readiness
from app.main import app
from app.schema_revision import expected_schema_revisions


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "Correct-horse-1"
DEFAULT_CLIENT_TIMEOUT_SECONDS = 60
_CLIENT_TIMEOUT_LIMIT_SECONDS = 600
_BACKUP_NAME = "backup.dump"
_RECOVERY_DIRECTORY_PREFIX = "skape-recovery-"
_CUSTOM_FORMAT_MAGIC = b"PGDMP"
_HASH_CHUNK_BYTES = 1024 * 1024
_SECRET_URL = re.compile(
    r"postgresql(?:\+\w+)?://\S+",
    re.IGNORECASE,
)
_CONTAINER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_DRILL = os.environ.get("SKAPE_RECOVERY_DRILL") == "1"
_URL = os.environ.get("SKAPE_TEST_DATABASE_URL", "").strip()
_REQUIRE = os.environ.get("SKAPE_REQUIRE_POSTGRES") == "1"


def drill_decision(drill, require, url, tools_present):
    """Return skip, or a failure message, or run."""

    if str(drill) != "1":
        return "skip"
    if str(require) != "1":
        return "SKAPE_REQUIRE_POSTGRES=1 is required"
    if not str(url or "").strip():
        return "SKAPE_TEST_DATABASE_URL is required"
    if not tools_present:
        return "pg_dump and pg_restore are required"
    return "run"


def _validated_disposable_name(module, name):
    if (
        name in module.FORBIDDEN_DATABASES
        or not module.DISPOSABLE_NAME.fullmatch(name or "")
    ):
        raise RuntimeError(
            "refusing to operate on a non-disposable database"
        )
    return name


def _load_disposable():
    path = Path(__file__).with_name("test_device_monitor_postgres.py")
    spec = importlib.util.spec_from_file_location(
        "skape_postgres_recovery_disposable",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _redact(payload, password):
    text_value = payload.decode("utf-8", errors="replace")
    cleaned = _SECRET_URL.sub("postgresql://...", text_value)
    if password:
        cleaned = cleaned.replace(password, "[redacted]")
    return cleaned.strip()


def _tool_prefix(tool):
    found = shutil.which(tool)
    if found:
        return [found], "host"
    container = os.environ.get("SKAPE_PG_DOCKER_CONTAINER", "").strip()
    if container:
        if not _CONTAINER_NAME.fullmatch(container):
            pytest.fail(
                "SKAPE_PG_DOCKER_CONTAINER is not a valid container name"
            )
        if shutil.which("docker") is None:
            pytest.fail("docker is required to run PostgreSQL client tools")
        return ["docker", "exec", "-i", container, tool], "docker"
    pytest.fail(
        f"{tool} is required on PATH, or set SKAPE_PG_DOCKER_CONTAINER "
        "to the disposable PostgreSQL container"
    )


def _client_invocation(tool):
    command, mode = _tool_prefix(tool)
    return command, mode


def _require_drill():
    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.fail("the recovery drill must run serially")
    decision = drill_decision(
        "1" if _DRILL else "0",
        "1" if _REQUIRE else "0",
        _URL,
        True,
    )
    if decision == "skip":
        pytest.skip("SKAPE_RECOVERY_DRILL is not set")
    if decision != "run":
        pytest.fail(decision)
    dump_command, dump_mode = _client_invocation("pg_dump")
    restore_command, restore_mode = _client_invocation("pg_restore")
    if dump_mode != restore_mode:
        pytest.fail("pg_dump and pg_restore must come from the same place")
    return dump_command, restore_command, dump_mode


def _client_timeout():
    raw = os.environ.get("SKAPE_PG_CLIENT_TIMEOUT_SECONDS")
    if raw is None or not str(raw).strip():
        return DEFAULT_CLIENT_TIMEOUT_SECONDS
    text_value = str(raw).strip()
    if (
        len(text_value) > 4
        or not text_value.isascii()
        or not text_value.isdigit()
    ):
        pytest.fail(
            "SKAPE_PG_CLIENT_TIMEOUT_SECONDS must be a positive integer"
        )
    value = int(text_value)
    if value < 1 or value > _CLIENT_TIMEOUT_LIMIT_SECONDS:
        pytest.fail(
            "SKAPE_PG_CLIENT_TIMEOUT_SECONDS must be from 1 to 600"
        )
    return value


def _client_label(command):
    for name in ("pg_dump", "pg_restore"):
        if name in command:
            return name
    return "PostgreSQL client"


def _stop_docker_tool(command):
    """Signal a client left running after the local Docker process exits."""

    if len(command) < 5 or command[0] != "docker" or command[1] != "exec":
        return
    container = command[3]
    tool = command[4]
    if tool not in {"pg_dump", "pg_restore"}:
        return
    if not _CONTAINER_NAME.fullmatch(container or ""):
        return
    subprocess.run(
        ["docker", "exec", container, "pkill", "-x", tool],
        capture_output=True,
        timeout=10,
        check=False,
    )


def _run_client(
    command,
    *,
    password="",
    stdin=None,
    env=None,
    mode="host",
    stdout_path=None,
):
    timeout = _client_timeout()
    stdout_handle = None
    try:
        if stdout_path is not None:
            stdout_handle = open(stdout_path, "wb")
            run_stdout = stdout_handle
        else:
            run_stdout = subprocess.PIPE
        run_arguments = {
            "stdout": run_stdout,
            "stderr": subprocess.PIPE,
            "env": env,
            "check": False,
            "timeout": timeout,
        }
        if isinstance(stdin, (bytes, bytearray)):
            run_arguments["input"] = stdin
        elif stdin is not None:
            run_arguments["stdin"] = stdin
        try:
            completed = subprocess.run(command, **run_arguments)
        except subprocess.TimeoutExpired:
            if mode == "docker":
                try:
                    _stop_docker_tool(command)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            raise pytest.fail.Exception(
                f"PostgreSQL client timed out after {timeout} seconds"
            ) from None
    finally:
        if stdout_handle is not None:
            stdout_handle.close()
    if completed.returncode != 0:
        detail_source = completed.stderr or completed.stdout or b""
        if not isinstance(detail_source, (bytes, bytearray)):
            detail_source = b""
        detail = _redact(detail_source, password)
        pytest.fail(
            f"{_client_label(command)} failed with status "
            f"{completed.returncode}"
            + (f": {detail}" if detail else "")
        )
    return completed


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_custom_format(path):
    size = path.stat().st_size
    if size <= 0:
        pytest.fail("pg_dump produced an empty backup")
    with path.open("rb") as handle:
        magic = handle.read(len(_CUSTOM_FORMAT_MAGIC))
    if magic != _CUSTOM_FORMAT_MAGIC:
        pytest.fail("pg_dump did not write a custom-format backup")
    return size


class BackupArtifact:
    def __init__(self, path, size, digest, backup_seconds):
        self.path = path
        self.size = size
        self.digest = digest
        self.backup_seconds = backup_seconds


def _verify_backup(artifact):
    if not artifact.path.is_file():
        pytest.fail("backup checksum does not match")
    size = artifact.path.stat().st_size
    digest = _sha256(artifact.path)
    if size != artifact.size or digest != artifact.digest:
        pytest.fail("backup checksum does not match")
    return digest


def _require_recovery_directory(directory):
    path = Path(directory)
    if (
        not path.is_dir()
        or path.is_symlink()
        or not path.name.startswith(_RECOVERY_DIRECTORY_PREFIX)
    ):
        pytest.fail(
            "refusing to write a backup outside a recovery directory"
        )
    return path


def _cleanup_recovery_directory(directory):
    if directory is None:
        return
    directory = Path(directory)
    if not directory.name.startswith(_RECOVERY_DIRECTORY_PREFIX):
        return
    if not directory.is_dir():
        return
    for child in directory.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
    directory.rmdir()


def _restrict_password_file(path):
    """Limit a host-mode password file on Unix.

    Windows does not honor this Unix mode. The caller still removes the
    file when the test ends, and the password is not passed as an
    argument.
    """

    if os.name == "posix":
        os.chmod(path, 0o600)
        mode = os.stat(path).st_mode & 0o777
        if mode != 0o600:
            path.unlink(missing_ok=True)
            pytest.fail(
                "PostgreSQL password file permissions could not be restricted"
            )
        return
    if os.name == "nt":
        return
    path.unlink(missing_ok=True)
    pytest.fail(
        "PostgreSQL password file permissions are not supported on this platform"
    )


def _pgpass(directory, parsed, password):
    host = parsed.host or ""
    port = parsed.port or 5432
    escaped = (
        password.replace("\\", "\\\\").replace(":", "\\:")
    )
    path = directory / "pgpass"
    path.write_text(
        f"{host}:{port}:*:{parsed.username}:{escaped}\n",
        encoding="utf-8",
    )
    _restrict_password_file(path)
    return path


def _child_env(parsed, mode, password, directory):
    env = os.environ.copy()
    env.pop("SKAPE_TEST_DATABASE_URL", None)
    env.pop("PGPASSWORD", None)
    if mode == "host":
        if not parsed.host or not parsed.username:
            pytest.fail(
                "the PostgreSQL test URL must include a host and user"
            )
        pgpass = _pgpass(directory, parsed, password)
        env["PGPASSFILE"] = str(pgpass)
    return env


def _connection_args(parsed, mode, database):
    if mode == "docker":
        return ["-U", parsed.username, "-d", database]
    return [
        "-h",
        parsed.host,
        "-p",
        str(parsed.port or 5432),
        "-U",
        parsed.username,
        "-d",
        database,
    ]


def _major(version_text):
    match = re.search(r"(\d+)", version_text)
    if match is None:
        pytest.fail("PostgreSQL client version could not be read")
    return int(match.group(1))


def _assert_client_can_dump(module, dump_command, mode, engine, name, env):
    _validated_disposable_name(module, name)
    with engine.connect() as connection:
        module._assert_identity(connection, name)
        server = connection.execute(
            text("SHOW server_version_num")
        ).scalar()
    completed = _run_client(
        dump_command + ["--version"],
        env=env,
        mode=mode,
    )
    client = _major(completed.stdout.decode("utf-8", errors="replace"))
    server_major = int(server) // 10000
    if client < server_major:
        pytest.fail(
            "pg_dump is older than the PostgreSQL server"
        )


def _dump_database(
    module,
    dump_command,
    mode,
    parsed,
    engine,
    name,
    env,
    directory,
):
    _require_recovery_directory(directory)
    _validated_disposable_name(module, name)
    _assert_client_can_dump(
        module,
        dump_command,
        mode,
        engine,
        name,
        env,
    )
    path = directory / _BACKUP_NAME
    password = parsed.password or ""
    started = time.perf_counter()
    _run_client(
        dump_command
        + ["-Fc", "--no-owner", "--no-acl"]
        + _connection_args(parsed, mode, name),
        password=password,
        env=env,
        mode=mode,
        stdout_path=path,
    )
    backup_seconds = time.perf_counter() - started
    size = _assert_custom_format(path)
    return BackupArtifact(path, size, _sha256(path), backup_seconds)


def _restore_stream(command, artifact, *, env, mode, password=""):
    _verify_backup(artifact)
    started = time.perf_counter()
    with artifact.path.open("rb") as handle:
        _run_client(
            command,
            password=password,
            stdin=handle,
            env=env,
            mode=mode,
        )
    return time.perf_counter() - started


def _restore_database(
    module,
    restore_command,
    mode,
    parsed,
    engine,
    name,
    artifact,
    env,
):
    _validated_disposable_name(module, name)
    _verify_backup(artifact)
    with engine.begin() as connection:
        module._assert_identity(connection, name)
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    password = parsed.password or ""
    return _restore_stream(
        restore_command
        + ["--no-owner", "--exit-on-error", "--single-transaction"]
        + _connection_args(parsed, mode, name),
        artifact,
        env=env,
        mode=mode,
        password=password,
    )


def _names(connection, statement):
    return connection.execute(text(statement)).scalars().all()


def _register(api, email, organization):
    response = api.post(
        "/api/v1/users/",
        json={
            "name": "Recovery Owner",
            "email": email,
            "password": PASSWORD,
            "organization_name": organization,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _auth(api, email):
    response = api.post(
        "/api/v1/users/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def quiet_monitor(monkeypatch):
    async def idle():
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            return

    monkeypatch.setattr("app.main.device_monitor", idle)


def _bind(monkeypatch, engine):
    factory = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    monkeypatch.setattr("app.database.SessionLocal", factory)
    monkeypatch.setattr("app.api.health.SessionLocal", factory)


@pytest.mark.parametrize(
    ("drill", "require", "url", "tools", "expected"),
    [
        ("0", "1", "present", True, "skip"),
        ("1", "0", "present", True, "SKAPE_REQUIRE_POSTGRES=1 is required"),
        ("1", "1", "  ", True, "SKAPE_TEST_DATABASE_URL is required"),
        ("1", "1", "", True, "SKAPE_TEST_DATABASE_URL is required"),
        ("1", "1", "present", False, "pg_dump and pg_restore are required"),
        ("1", "1", "present", True, "run"),
    ],
)
def test_recovery_drill_configuration(
    drill,
    require,
    url,
    tools,
    expected,
):
    assert drill_decision(drill, require, url, tools) == expected


@pytest.mark.parametrize(
    "name",
    ["skape", "postgres", "template0", "template1", "", "skape_test_admin_db"],
)
def test_recovery_refuses_protected_database_names(name):
    module = _load_disposable()
    with pytest.raises(
        RuntimeError,
        match="non-disposable",
    ):
        _validated_disposable_name(module, name)


@pytest.mark.parametrize(
    "name",
    ["skape", "postgres", "template0", "template1"],
)
def test_drop_helper_refuses_protected_database_without_connecting(name):
    module = _load_disposable()
    attempts = []

    class AdminEngine:
        def connect(self):
            attempts.append(name)
            raise AssertionError("protected database drop opened a connection")

    with pytest.raises(RuntimeError, match="refusing to drop database"):
        module._drop_database(AdminEngine(), name)
    assert attempts == []


def test_posix_password_file_must_be_owner_only(tmp_path, monkeypatch):
    path = tmp_path / "pgpass"
    path.write_text("unused\n", encoding="utf-8")
    monkeypatch.setattr(os, "name", "posix")
    requested = []
    monkeypatch.setattr(
        os,
        "chmod",
        lambda target, mode: requested.append(mode),
    )

    class Result:
        st_mode = 0o100600

    monkeypatch.setattr(os, "stat", lambda target: Result())
    _restrict_password_file(path)
    assert requested == [0o600]
    assert path.exists()


def test_posix_password_file_is_removed_when_restriction_fails(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "pgpass"
    path.write_text("unused\n", encoding="utf-8")
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(os, "chmod", lambda target, mode: None)

    class Result:
        st_mode = 0o100644

    monkeypatch.setattr(os, "stat", lambda target: Result())
    with pytest.raises(
        pytest.fail.Exception,
        match="could not be restricted",
    ):
        _restrict_password_file(path)
    assert not path.exists()


def test_windows_password_file_does_not_use_unix_mode(tmp_path, monkeypatch):
    path = tmp_path / "pgpass"
    path.write_text("unused\n", encoding="utf-8")
    monkeypatch.setattr(os, "name", "nt")
    requested = []
    monkeypatch.setattr(
        os,
        "chmod",
        lambda target, mode: requested.append(mode),
    )
    _restrict_password_file(path)
    assert requested == []
    assert path.exists()


def test_client_timeout_rejects_non_integers(monkeypatch):
    monkeypatch.setenv("SKAPE_PG_CLIENT_TIMEOUT_SECONDS", "15 seconds")
    with pytest.raises(
        pytest.fail.Exception,
        match="positive integer",
    ) as caught:
        _client_timeout()
    assert "15 seconds" not in str(caught.value)


def test_client_timeout_reports_a_safe_message(monkeypatch):
    def timed_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 1))

    monkeypatch.setattr(subprocess, "run", timed_out)
    monkeypatch.delenv("SKAPE_PG_CLIENT_TIMEOUT_SECONDS", raising=False)
    secret = "synthetic-password"
    with pytest.raises(
        pytest.fail.Exception,
        match="timed out after 60 seconds",
    ) as caught:
        _run_client(
            [
                "pg_dump",
                "-h",
                "127.0.0.1",
                "-d",
                "skape_test_0123456789abcdef",
            ],
            password=secret,
            mode="host",
        )
    message = str(caught.value)
    assert secret not in message
    assert "127.0.0.1" not in message
    assert "postgresql://" not in message


def test_docker_client_timeout_signals_the_container_tool(monkeypatch):
    signaled = []

    def routed(command, **kwargs):
        if "pkill" in command:
            signaled.append(command)
            return subprocess.CompletedProcess(command, 0, b"", b"")
        raise subprocess.TimeoutExpired(["client"], 1)

    monkeypatch.setattr(subprocess, "run", routed)
    monkeypatch.delenv("SKAPE_PG_CLIENT_TIMEOUT_SECONDS", raising=False)
    with pytest.raises(
        pytest.fail.Exception,
        match="timed out after 60 seconds",
    ) as caught:
        _run_client(
            [
                "docker",
                "exec",
                "-i",
                "skape-pg-test",
                "pg_restore",
                "-d",
                "skape_test_0123456789abcdef",
            ],
            password="synthetic-password",
            mode="docker",
        )
    assert signaled == [[
        "docker",
        "exec",
        "skape-pg-test",
        "pkill",
        "-x",
        "pg_restore",
    ]]
    assert "synthetic-password" not in str(caught.value)


def test_empty_backup_is_rejected(tmp_path):
    path = tmp_path / _BACKUP_NAME
    path.write_bytes(b"")
    with pytest.raises(pytest.fail.Exception, match="empty backup"):
        _assert_custom_format(path)


def test_non_custom_backup_is_rejected(tmp_path):
    path = tmp_path / _BACKUP_NAME
    path.write_bytes(b"not-a-dump")
    with pytest.raises(
        pytest.fail.Exception,
        match="custom-format",
    ) as caught:
        _assert_custom_format(path)
    assert "not-a-dump" not in str(caught.value)


def test_checksum_mismatch_does_not_restore(monkeypatch, tmp_path):
    path = tmp_path / _BACKUP_NAME
    path.write_bytes(b"PGDMPsynthetic-archive")
    artifact = BackupArtifact(
        path,
        path.stat().st_size,
        _sha256(path),
        0.0,
    )
    path.write_bytes(b"PGDMPsynthetic-archivX")
    invoked = []

    def explode(command, **kwargs):
        invoked.append(command)
        raise AssertionError("pg_restore was invoked")

    monkeypatch.setattr(subprocess, "run", explode)
    with pytest.raises(
        pytest.fail.Exception,
        match="backup checksum does not match",
    ):
        _restore_stream(
            ["pg_restore", "-d", "skape_test_0123456789abcdef"],
            artifact,
            env={},
            mode="host",
        )
    assert invoked == []


def test_checksum_accepts_the_same_file(tmp_path):
    path = tmp_path / _BACKUP_NAME
    path.write_bytes(b"PGDMPsame-archive")
    artifact = BackupArtifact(
        path,
        path.stat().st_size,
        _sha256(path),
        0.01,
    )
    assert _verify_backup(artifact) == artifact.digest


def test_cleanup_removes_backup_and_password_file(tmp_path):
    directory = tmp_path / "skape-recovery-unit"
    directory.mkdir()
    (directory / _BACKUP_NAME).write_bytes(b"PGDMPpartial")
    (directory / "pgpass").write_text("unused\n", encoding="utf-8")
    _cleanup_recovery_directory(directory)
    assert not directory.exists()


def test_dump_rejects_an_invalid_directory_before_writing(
    tmp_path,
    monkeypatch,
):
    directory = tmp_path / "other-dir"
    directory.mkdir()
    marker = directory / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    invoked = []

    def explode(command, **kwargs):
        invoked.append(command)
        raise AssertionError("client was invoked")

    monkeypatch.setattr(subprocess, "run", explode)
    with pytest.raises(
        pytest.fail.Exception,
        match="outside a recovery directory",
    ):
        _dump_database(
            None,
            ["pg_dump"],
            "host",
            None,
            None,
            "skape",
            {},
            directory,
        )
    assert invoked == []
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not (directory / _BACKUP_NAME).exists()


def test_cleanup_leaves_an_unrelated_directory(tmp_path):
    directory = tmp_path / "other-dir"
    directory.mkdir()
    marker = directory / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    _cleanup_recovery_directory(directory)
    assert marker.read_text(encoding="utf-8") == "keep"


def test_logical_backup_restores_schema_and_workflow(
    quiet_monitor,
    monkeypatch,
):
    dump_command, restore_command, mode = _require_drill()
    module = _load_disposable()
    parsed = module._assert_safe_admin_url(_URL)
    directory = Path(tempfile.mkdtemp(prefix="skape-recovery-"))
    try:
        env = _child_env(parsed, mode, parsed.password or "", directory)
        with module.disposable_database("head") as source:
            _validated_disposable_name(module, source.name)
            _bind(monkeypatch, source.engine)
            with TestClient(app) as api:
                owner = _register(
                    api,
                    "recovery-owner-a@example.com",
                    "Recovery Org A",
                )
                outsider = _register(
                    api,
                    "recovery-owner-b@example.com",
                    "Recovery Org B",
                )
                owner_headers = _auth(api, owner["email"])
                created = api.post(
                    "/api/v1/projects/",
                    headers=owner_headers,
                    json={
                        "name": "Recovery Pump",
                        "description": "Synthetic recovery fixture",
                    },
                )
                assert created.status_code == 200, created.text
                project_id = created.json()["id"]
            total_started = time.perf_counter()
            artifact = _dump_database(
                module,
                dump_command,
                mode,
                parsed,
                source.engine,
                source.name,
                env,
                directory,
            )
            assert artifact.path == directory / _BACKUP_NAME
            assert artifact.size > 0
            assert _sha256(artifact.path) == artifact.digest
            with module.disposable_database(None) as destination:
                _validated_disposable_name(module, destination.name)
                assert destination.name != source.name
                restore_seconds = _restore_database(
                    module,
                    restore_command,
                    mode,
                    parsed,
                    destination.engine,
                    destination.name,
                    artifact,
                    env,
                )
                with destination.engine.connect() as connection:
                    module._assert_identity(connection, destination.name)
                    current = connection.execute(
                        text("SELECT current_database()")
                    ).scalar()
                    assert current == destination.name
                    assert current != source.name
                    stored = set(
                        _names(
                            connection,
                            "SELECT version_num FROM alembic_version",
                        )
                    )
                    assert stored == set(expected_schema_revisions())
                    assert _names(
                        connection,
                        "SELECT email FROM users ORDER BY email",
                    ) == [
                        "recovery-owner-a@example.com",
                        "recovery-owner-b@example.com",
                    ]
                    assert _names(
                        connection,
                        "SELECT name FROM projects ORDER BY name",
                    ) == ["Recovery Pump"]
                _bind(monkeypatch, destination.engine)
                with TestClient(app) as api:
                    owner_headers = _auth(
                        api,
                        "recovery-owner-a@example.com",
                    )
                    outsider_headers = _auth(
                        api,
                        "recovery-owner-b@example.com",
                    )
                    visible = api.get(
                        "/api/v1/projects/",
                        headers=owner_headers,
                    )
                    assert visible.status_code == 200
                    assert [item["name"] for item in visible.json()] == [
                        "Recovery Pump"
                    ]
                    hidden = api.get(
                        "/api/v1/projects/",
                        headers=outsider_headers,
                    )
                    assert hidden.status_code == 200
                    assert hidden.json() == []
                    denied = api.get(
                        f"/api/v1/projects/{project_id}",
                        headers=outsider_headers,
                    )
                    assert denied.status_code == 404
                    follow_up = api.post(
                        "/api/v1/projects/",
                        headers=owner_headers,
                        json={
                            "name": "Restored Follow-up",
                            "description": "Created after restore",
                        },
                    )
                    assert follow_up.status_code == 200, follow_up.text
                    monkeypatch.setenv("SKAPE_ENV", "production")
                    ready = readiness(
                        type(
                            "Request",
                            (),
                            {"state": type("State", (), {"request_id": "restore-ready"})()},
                        )()
                    )
                assert ready["status"] == "ready"
                with destination.engine.connect() as connection:
                    module._assert_identity(connection, destination.name)
                    assert _names(
                        connection,
                        "SELECT name FROM projects ORDER BY name",
                    ) == ["Recovery Pump", "Restored Follow-up"]
                with source.engine.connect() as connection:
                    module._assert_identity(connection, source.name)
                    assert _names(
                        connection,
                        "SELECT name FROM projects ORDER BY name",
                    ) == ["Recovery Pump"]
            total_seconds = time.perf_counter() - total_started
            assert artifact.backup_seconds >= 0
            assert restore_seconds >= 0
            assert total_seconds >= 0
            assert (
                total_seconds + 1e-6
                >= artifact.backup_seconds + restore_seconds
            )
            print(
                "recovery-drill "
                f"backup_seconds={artifact.backup_seconds:.6f} "
                f"restore_seconds={restore_seconds:.6f} "
                f"total_seconds={total_seconds:.6f} "
                f"sha256={artifact.digest}",
                flush=True,
            )
    finally:
        _cleanup_recovery_directory(directory)


def test_failed_restore_does_not_drop_protected_databases(monkeypatch):
    dump_command, restore_command, mode = _require_drill()
    module = _load_disposable()
    parsed = module._assert_safe_admin_url(_URL)
    directory = Path(tempfile.mkdtemp(prefix="skape-recovery-"))

    def protected_snapshot():
        engine = create_engine(
            _URL,
            poolclass=NullPool,
            isolation_level="AUTOCOMMIT",
        )
        try:
            with engine.connect() as connection:
                current = connection.execute(
                    text("SELECT current_database()")
                ).scalar()
                if (
                    current in module.FORBIDDEN_DATABASES
                    or module.DISPOSABLE_NAME.fullmatch(current or "")
                ):
                    raise RuntimeError(
                        "refusing to inspect from an unsafe database"
                    )
                present = set(
                    connection.execute(
                        text(
                            "SELECT datname FROM pg_database "
                            "WHERE datname IN "
                            "('postgres', 'template0', 'template1')"
                        )
                    ).scalars().all()
                )
                disposable = [
                    name
                    for name in connection.execute(
                        text("SELECT datname FROM pg_database")
                    ).scalars().all()
                    if module.DISPOSABLE_NAME.fullmatch(name)
                ]
                return present, disposable
        finally:
            engine.dispose()

    real_run = subprocess.run

    def fail_restore(command, **kwargs):
        if command and "pg_restore" in command:
            return subprocess.CompletedProcess(
                command,
                1,
                b"",
                b"restore failed",
            )
        return real_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", fail_restore)
    before, _before_disposable = protected_snapshot()
    try:
        env = _child_env(parsed, mode, parsed.password or "", directory)
        with module.disposable_database("head") as source:
            artifact = _dump_database(
                module,
                dump_command,
                mode,
                parsed,
                source.engine,
                source.name,
                env,
                directory,
            )
            assert artifact.path.is_file()
            with module.disposable_database(None) as destination:
                with pytest.raises(pytest.fail.Exception):
                    _restore_database(
                        module,
                        restore_command,
                        mode,
                        parsed,
                        destination.engine,
                        destination.name,
                        artifact,
                        env,
                    )
        after, disposable = protected_snapshot()
        assert after == before == {"postgres", "template0", "template1"}
        assert disposable == []
        assert artifact.path.is_file()
    finally:
        _cleanup_recovery_directory(directory)
    assert not directory.exists()
