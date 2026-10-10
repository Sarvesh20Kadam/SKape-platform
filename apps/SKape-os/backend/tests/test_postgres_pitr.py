"""Isolated PostgreSQL 16 point-in-time recovery proof.

The live proof runs only when SKAPE_PITR_DRILL=1. It starts a new
PostgreSQL 16 cluster with WAL archiving enabled at first startup,
takes a base backup, commits two synthetic transactions, and recovers
a second instance to a source timestamp strictly between them.

It does not use the shared disposable test server. Cleanup removes
only containers, volumes, and networks created by that run.
"""

import asyncio
import json
import os
import re
import secrets
import shutil
import subprocess
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.api.health import readiness
from app.main import app
from app.schema_revision import expected_schema_revisions


_PITR = os.environ.get("SKAPE_PITR_DRILL") == "1"
PROOF_LABEL = "pitr"
PREFIX = "skape-pitr-"
SOURCE_NAME = "skape-pitr-source"
RECOVERED_NAME = "skape-pitr-recovered"
SOURCE_VOLUME = "skape-pitr-source-data"
ARCHIVE_VOLUME = "skape-pitr-archive"
RESTORE_VOLUME = "skape-pitr-restore-data"
NETWORK_NAME = "skape-pitr-net"
ADMIN_DATABASE = "skape_pitr_admin"
ROLE_NAME = "skape_pitr"
SOURCE_PORT = 55433
RECOVERY_PORT = 55434
SHARED_CONTAINER = "skape-pg-test"
SHARED_PORT = 55432
IMAGE = "postgres:16"
PASSWORD = "Correct-horse-1"
PROJECT_A = "PITR Transaction A"
PROJECT_B = "PITR Transaction B"
_PROOF_NAME = re.compile(r"^skape-pitr-[a-z0-9-]{1,48}$")
_DISPOSABLE_NAME = re.compile(r"^skape_test_[0-9a-f]{16}$")
_TARGET_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}\+0000$"
)
_WAL_FILE = re.compile(r"^[0-9A-F]{24}$")
_SECRET_URL = re.compile(
    r"postgres(?:ql)?(?:\+\w+)?://\S+",
    re.IGNORECASE,
)
PROTECTED_NAMES = frozenset(
    {
        SHARED_CONTAINER,
        "bridge",
        "host",
        "none",
        "postgres",
        "template0",
        "template1",
        "skape",
    }
)
SOURCE_BOOT = """
set -e
mkdir -p /var/lib/postgresql/archive /var/lib/postgresql/restore
chown postgres:postgres /var/lib/postgresql/archive /var/lib/postgresql/restore
chmod 700 /var/lib/postgresql/archive /var/lib/postgresql/restore
exec docker-entrypoint.sh postgres \\
  -c wal_level=replica \\
  -c archive_mode=on \\
  -c archive_timeout=10 \\
  -c max_wal_senders=10 \\
  -c hot_standby=on \\
  -c timezone=UTC \\
  -c cluster_name=skape-pitr-source \\
  -c archive_command='test ! -f /var/lib/postgresql/archive/%f && cp %p /var/lib/postgresql/archive/%f'
""".replace("\r\n", "\n").replace("\r", "\n").strip()


class ProofError(RuntimeError):
    """A proof step failed with an already redacted message."""


def validate_target_timestamp(value):
    """Accept only a UTC timestamp safe to place in recovery configuration."""

    if not isinstance(value, str) or not _TARGET_TIME.fullmatch(value):
        raise ProofError(
            "recovery target timestamp is not a UTC timestamp"
        )
    return value


def removal_decision(name, inspected_name, label, owned_names, protected):
    """Return remove, or raise without selecting a foreign resource."""

    inspected = (inspected_name or "").strip().lstrip("/")
    protected_names = set(protected)
    if (
        name in protected_names
        or inspected in protected_names
        or name == SHARED_CONTAINER
        or inspected == SHARED_CONTAINER
    ):
        raise ProofError("refusing to remove a protected resource")
    if name not in owned_names:
        raise ProofError(
            "refusing to remove a resource this proof did not create"
        )
    if inspected != name:
        raise ProofError(
            "refusing to remove a resource whose name changed"
        )
    if not _PROOF_NAME.fullmatch(name):
        raise ProofError(
            "refusing to remove a resource outside the proof namespace"
        )
    if label != PROOF_LABEL:
        raise ProofError(
            "refusing to remove a resource without the proof label"
        )
    return "remove"


def validate_source_mounts(
    mounts,
    *,
    data_volume,
    archive_volume,
    restore_volume,
    protected_names,
):
    """Require three distinct writable proof volumes and nothing else."""

    volumes = (data_volume, archive_volume, restore_volume)
    if len(set(volumes)) != 3:
        raise ProofError("proof volumes are not distinct")
    if any(volume in protected_names for volume in volumes):
        raise ProofError("proof mount reuses a protected volume")
    by_destination = {}
    for mount in mounts:
        destination = mount.get("Destination")
        if destination in by_destination:
            raise ProofError("duplicate mount destination")
        by_destination[destination] = mount
    expected = {
        "/var/lib/postgresql/data": data_volume,
        "/var/lib/postgresql/archive": archive_volume,
        "/var/lib/postgresql/restore": restore_volume,
    }
    if set(by_destination) != set(expected):
        raise ProofError("source mounts are not the three proof volumes")
    for destination, volume in expected.items():
        mount = by_destination[destination]
        if mount.get("Name") != volume or mount.get("RW") is not True:
            raise ProofError(
                "source mount does not match the proof volume"
            )
        if mount.get("Type") != "volume":
            raise ProofError("source mount is not a Docker volume")
    return "ok"


def validate_recovered_mounts(
    mounts,
    *,
    restore_volume,
    archive_volume,
    source_volume,
    protected_names,
):
    """Require the backup as data and the archive mounted read-only."""

    if restore_volume == archive_volume or restore_volume == source_volume:
        raise ProofError("recovered volumes are not distinct")
    if any(
        volume in protected_names
        for volume in (restore_volume, archive_volume, source_volume)
    ):
        raise ProofError("recovered mount reuses a protected volume")
    by_destination = {}
    for mount in mounts:
        destination = mount.get("Destination")
        if destination in by_destination:
            raise ProofError("duplicate mount destination")
        by_destination[destination] = mount
        if mount.get("Name") in protected_names or mount.get("Name") == source_volume:
            raise ProofError(
                "recovered instance mounts a protected or source volume"
            )
    expected = {
        "/var/lib/postgresql/data": (restore_volume, True),
        "/archive": (archive_volume, False),
    }
    if set(by_destination) != set(expected):
        raise ProofError("recovered mounts are not the backup and archive")
    for destination, (volume, writable) in expected.items():
        mount = by_destination[destination]
        if (
            mount.get("Name") != volume
            or mount.get("RW") is not writable
            or mount.get("Type") != "volume"
        ):
            raise ProofError(
                "recovered mount does not match the proof volume"
            )
    return "ok"


def recovery_configuration(target):
    """Shell script that arms PITR only inside the restore directory."""

    checked = validate_target_timestamp(target)
    return "\n".join(
        [
            "set -e",
            "data_dev=$(stat -c %m /var/lib/postgresql/data)",
            "archive_dev=$(stat -c %m /var/lib/postgresql/archive)",
            "restore_dev=$(stat -c %m /var/lib/postgresql/restore)",
            'test "$data_dev" != "$archive_dev"',
            'test "$data_dev" != "$restore_dev"',
            'test "$archive_dev" != "$restore_dev"',
            "printf '\\n' >> /var/lib/postgresql/restore/postgresql.auto.conf",
            "cat >> /var/lib/postgresql/restore/postgresql.auto.conf << 'EOF'",
            "restore_command = 'cp /archive/%f %p'",
            f"recovery_target_time = '{checked}'",
            "recovery_target_action = 'pause'",
            "recovery_target_inclusive = on",
            "EOF",
            "touch /var/lib/postgresql/restore/recovery.signal",
            "test -f /var/lib/postgresql/restore/recovery.signal",
            "test -f /var/lib/postgresql/restore/PG_VERSION",
            "test ! -f /var/lib/postgresql/data/recovery.signal",
        ]
    )


def _normalize_id(value):
    text_value = (value or "").strip()
    if text_value.startswith("sha256:"):
        return text_value[len("sha256:") :]
    return text_value


def _redact(payload, password):
    cleaned = _SECRET_URL.sub("postgresql://...", str(payload))
    if password:
        cleaned = cleaned.replace(password, "[redacted]")
    return cleaned.strip()


def _docker_result(args, timeout=120):
    try:
        return subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            check=False,
            text=True,
        )
    except subprocess.TimeoutExpired:
        raise ProofError("docker command timed out") from None


def _safe_command(args):
    """Identify a docker command without values that can carry a secret."""

    hidden_flags = {"-e", "--env"}
    shown = []
    skip_value = False
    for arg in args:
        if skip_value:
            skip_value = False
            shown.append("[redacted]")
            continue
        if arg in hidden_flags:
            skip_value = True
            shown.append(arg)
            continue
        if (
            "PASSWORD" in arg
            or "://" in arg
            or arg.startswith("postgresql")
        ):
            shown.append("[redacted]")
            continue
        shown.append(arg)
    return " ".join(shown[:18])


def _docker(args, timeout=120, password=""):
    completed = _docker_result(args, timeout=timeout)
    if completed.returncode != 0:
        detail = _redact(completed.stderr or completed.stdout, password)
        label = _safe_command(args)
        raise ProofError(
            f"docker command failed ({completed.returncode}) {label}: "
            f"{detail[:800] or 'no output'}"
        )
    return completed.stdout


def _names(kind):
    if kind == "container":
        command = ["docker", "ps", "-a", "--format", "{{.Names}}"]
    elif kind == "volume":
        command = ["docker", "volume", "ls", "--format", "{{.Name}}"]
    elif kind == "network":
        command = ["docker", "network", "ls", "--format", "{{.Name}}"]
    else:
        raise ProofError("unknown docker resource kind")
    output = _docker(command)
    return {line.strip() for line in output.splitlines() if line.strip()}


def _port_is_free(port):
    import socket

    if port in {5432, SHARED_PORT}:
        raise ProofError("refusing to bind the shared database port")
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", port))
    except OSError:
        return False
    finally:
        probe.close()
    return True


class ProofResources:
    """Create and remove only the resources owned by one proof run."""

    def __init__(self):
        self.owned = []
        self.protected = set(PROTECTED_NAMES)
        self.snapshot = {
            "container": set(),
            "volume": set(),
            "network": set(),
        }
        self.password = ""
        self.captured = False
        self._closed = False

    def capture(self):
        self.snapshot = {
            "container": _names("container"),
            "volume": _names("volume"),
            "network": _names("network"),
        }
        self.protected.update(self.snapshot["container"])
        self.protected.update(self.snapshot["volume"])
        self.protected.update(self.snapshot["network"])
        self.captured = True
        shared = _docker(
            [
                "docker",
                "inspect",
                SHARED_CONTAINER,
                "--format",
                "{{.Id}}|{{.State.Status}}|{{.HostConfig.PortBindings}}|{{range .Mounts}}{{.Name}};{{end}}",
            ]
        ).strip()
        self.shared_identity = shared
        return shared

    def _require_fresh(self, kind, name):
        if not _PROOF_NAME.fullmatch(name):
            raise ProofError(
                "refusing to create a resource outside the proof namespace"
            )
        if name in self.snapshot[kind] or name in self.protected:
            raise ProofError(
                "refusing to use a resource that already exists"
            )
        existing = _names(kind)
        if name in existing:
            raise ProofError(
                "refusing to use a resource that already exists"
            )

    def create_volume(self, name):
        self._require_fresh("volume", name)
        _docker(
            [
                "docker",
                "volume",
                "create",
                "--label",
                f"skape.proof={PROOF_LABEL}",
                name,
            ]
        )
        identity = self._confirm("volume", name)
        self.owned.append(("volume", name, identity))
        return identity

    def create_network(self, name):
        self._require_fresh("network", name)
        _docker(
            [
                "docker",
                "network",
                "create",
                "--label",
                f"skape.proof={PROOF_LABEL}",
                name,
            ]
        )
        identity = self._confirm("network", name)
        self.owned.append(("network", name, identity))
        return identity

    def own_container(self, name, container_id):
        if not _PROOF_NAME.fullmatch(name):
            raise ProofError(
                "refusing to own a container outside the proof namespace"
            )
        if name in self.snapshot["container"]:
            raise ProofError(
                "refusing to own a container that already existed"
            )
        identity = self._confirm("container", name)
        if identity != _normalize_id(container_id):
            raise ProofError(
                "refusing to own a container id that does not match"
            )
        self.owned.append(("container", name, identity))
        return identity

    def _confirm(self, kind, name):
        templates = {
            "container": '{{.Id}}|{{.Name}}|{{index .Config.Labels "skape.proof"}}',
            "volume": '{{.Name}}|{{.Name}}|{{index .Labels "skape.proof"}}',
            "network": '{{.Id}}|{{.Name}}|{{index .Labels "skape.proof"}}',
        }
        output = _docker(
            [
                "docker",
                "inspect",
                "--format",
                templates[kind],
                name,
            ]
        ).strip()
        identity, inspected, label = output.split("|", 2)
        removal_decision(
            name,
            inspected,
            label,
            {name},
            self.protected,
        )
        if kind == "volume":
            return name
        return _normalize_id(identity)

    def cleanup(self):
        """Remove owned resources. A name mismatch is left in place."""

        if self._closed:
            return []
        errors = []
        if self.captured:
            for kind, name in (
                ("container", SOURCE_NAME),
                ("container", RECOVERED_NAME),
                ("volume", SOURCE_VOLUME),
                ("volume", ARCHIVE_VOLUME),
                ("volume", RESTORE_VOLUME),
                ("network", NETWORK_NAME),
            ):
                try:
                    self._adopt(kind, name)
                except ProofError as exc:
                    errors.append(str(exc))
        kinds = {"container": [], "volume": [], "network": []}
        for kind, name, identity in self.owned:
            kinds[kind].append((name, identity))
        for kind in ("container", "volume", "network"):
            for name, identity in kinds[kind]:
                try:
                    self._remove(kind, name, identity)
                except ProofError as exc:
                    errors.append(str(exc))
        self._closed = True
        return errors

    def _adopt(self, kind, name):
        """Own a labeled proof resource that this run created after the snapshot."""

        if name in self.snapshot[kind]:
            return
        if any(item[1] == name for item in self.owned):
            return
        templates = {
            "container": '{{.Id}}|{{.Name}}|{{index .Config.Labels "skape.proof"}}',
            "volume": '{{.Name}}|{{.Name}}|{{index .Labels "skape.proof"}}',
            "network": '{{.Id}}|{{.Name}}|{{index .Labels "skape.proof"}}',
        }
        completed = _docker_result(
            ["docker", "inspect", "--format", templates[kind], name]
        )
        if completed.returncode != 0:
            return
        identity, inspected, label = completed.stdout.strip().split("|", 2)
        removal_decision(
            name,
            inspected,
            label,
            {name},
            self.protected,
        )
        stored = name if kind == "volume" else _normalize_id(identity)
        self.owned.append((kind, name, stored))

    def _remove(self, kind, name, identity):
        templates = {
            "container": '{{.Name}}|{{index .Config.Labels "skape.proof"}}',
            "volume": '{{.Name}}|{{index .Labels "skape.proof"}}',
            "network": '{{.Name}}|{{index .Labels "skape.proof"}}',
        }
        completed = _docker_result(
            ["docker", "inspect", "--format", templates[kind], identity]
        )
        if completed.returncode != 0:
            return
        inspected, _, label = completed.stdout.strip().partition("|")
        removal_decision(
            name,
            inspected,
            label,
            {item[1] for item in self.owned},
            self.protected,
        )
        if kind == "container":
            command = ["docker", "rm", "-f", identity]
        elif kind == "volume":
            command = ["docker", "volume", "rm", identity]
        else:
            command = ["docker", "network", "rm", identity]
        _docker(command, password=self.password)

    def shared_unchanged(self):
        current = _docker(
            [
                "docker",
                "inspect",
                SHARED_CONTAINER,
                "--format",
                "{{.Id}}|{{.State.Status}}|{{.HostConfig.PortBindings}}|{{range .Mounts}}{{.Name}};{{end}}",
            ]
        ).strip()
        if current != self.shared_identity:
            raise ProofError("shared test server changed during the proof")
        return current


def _engine(password, port, database):
    if port in {5432, SHARED_PORT}:
        raise ProofError("refusing to connect to the shared database port")
    if database in PROTECTED_NAMES:
        raise ProofError("refusing to connect to a protected database")
    url = URL.create(
        "postgresql+psycopg2",
        username=ROLE_NAME,
        password=password,
        host="127.0.0.1",
        port=port,
        database=database,
    )
    return create_engine(
        url,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5},
    )


def _assert_current(connection, database):
    current = connection.execute(text("SELECT current_database()")).scalar()
    if current != database or current in PROTECTED_NAMES:
        raise ProofError("refusing to use an unexpected database")
    return current


def _wait_ready(container, database):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        completed = _docker_result(
            [
                "docker",
                "exec",
                container,
                "pg_isready",
                "-U",
                ROLE_NAME,
                "-d",
                database,
            ],
            timeout=15,
        )
        if completed.returncode == 0:
            return
        status = _docker(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Status}}",
                container,
            ]
        ).strip()
        if status not in {"created", "running"}:
            logs = _docker_result(
                ["docker", "logs", "--tail", "40", container],
                timeout=20,
            )
            detail = _redact(
                (logs.stderr or "") + (logs.stdout or ""),
                "",
            )
            raise ProofError(
                f"proof server exited before it was ready: {detail[:800]}"
            )
        time.sleep(1)
    raise ProofError("proof server did not become ready")


def _psql(container, database, statement):
    return _docker(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-U",
            ROLE_NAME,
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            "-tAc",
            statement,
        ]
    ).strip()


def _distinct_devices(container):
    script = (
        "data=$(stat -c %m /var/lib/postgresql/data); "
        "archive=$(stat -c %m /var/lib/postgresql/archive); "
        "restore=$(stat -c %m /var/lib/postgresql/restore); "
        'test "$data" != "$archive"; '
        'test "$data" != "$restore"; '
        'test "$archive" != "$restore"'
    )
    _docker(["docker", "exec", container, "bash", "-c", script])


def _archive_names(container):
    output = _docker(
        [
            "docker",
            "exec",
            container,
            "bash",
            "-c",
            "ls -1 /var/lib/postgresql/archive 2>/dev/null || true",
        ]
    )
    return {
        line.strip()
        for line in output.splitlines()
        if _WAL_FILE.fullmatch(line.strip() or "")
    }


def _dir_bytes(container, path):
    output = _docker(
        ["docker", "exec", container, "du", "-sb", path]
    ).strip()
    return int(output.split()[0])


def _mounts(container):
    output = _docker(["docker", "inspect", "--format", "{{json .Mounts}}", container])
    return json.loads(output)


def _bind(monkeypatch, engine):
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.database.SessionLocal", factory)
    monkeypatch.setattr("app.api.health.SessionLocal", factory)


def _register(api, email, organization):
    response = api.post(
        "/api/v1/users/",
        json={
            "name": "PITR Owner",
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
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def quiet_monitor(monkeypatch):
    async def idle():
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            return

    monkeypatch.setattr("app.main.device_monitor", idle)


def test_removal_refuses_protected_and_foreign_resources():
    owned = {SOURCE_NAME}
    protected = {SHARED_CONTAINER, "e1a4e92a6c69c7b76dfac1342c6f7dae"}
    assert (
        removal_decision(
            SOURCE_NAME,
            f"/{SOURCE_NAME}",
            PROOF_LABEL,
            owned,
            protected,
        )
        == "remove"
    )
    with pytest.raises(ProofError, match="protected"):
        removal_decision(
            SHARED_CONTAINER,
            SHARED_CONTAINER,
            PROOF_LABEL,
            {SHARED_CONTAINER},
            protected,
        )
    with pytest.raises(ProofError, match="did not create"):
        removal_decision(
            SOURCE_VOLUME,
            SOURCE_VOLUME,
            PROOF_LABEL,
            owned,
            protected,
        )
    with pytest.raises(ProofError, match="name changed"):
        removal_decision(
            SOURCE_NAME,
            "skape-pitr-other",
            PROOF_LABEL,
            owned,
            protected,
        )
    with pytest.raises(ProofError, match="proof label"):
        removal_decision(
            SOURCE_NAME,
            SOURCE_NAME,
            "other",
            owned,
            protected,
        )


def test_mount_plan_rejects_shared_volumes_and_shared_archive():
    protected = {"e1a4e92a6c69c7b76dfac1342c6f7dae"}
    mounts = [
        {"Destination": "/var/lib/postgresql/data", "Name": SOURCE_VOLUME, "RW": True, "Type": "volume"},
        {"Destination": "/var/lib/postgresql/archive", "Name": ARCHIVE_VOLUME, "RW": True, "Type": "volume"},
        {"Destination": "/var/lib/postgresql/restore", "Name": RESTORE_VOLUME, "RW": True, "Type": "volume"},
    ]
    assert (
        validate_source_mounts(
            mounts,
            data_volume=SOURCE_VOLUME,
            archive_volume=ARCHIVE_VOLUME,
            restore_volume=RESTORE_VOLUME,
            protected_names=protected,
        )
        == "ok"
    )
    with pytest.raises(ProofError, match="protected"):
        validate_source_mounts(
            mounts,
            data_volume=next(iter(protected)),
            archive_volume=ARCHIVE_VOLUME,
            restore_volume=RESTORE_VOLUME,
            protected_names=protected,
        )
    recovered = [
        {"Destination": "/var/lib/postgresql/data", "Name": RESTORE_VOLUME, "RW": True, "Type": "volume"},
        {"Destination": "/archive", "Name": ARCHIVE_VOLUME, "RW": False, "Type": "volume"},
    ]
    assert (
        validate_recovered_mounts(
            recovered,
            restore_volume=RESTORE_VOLUME,
            archive_volume=ARCHIVE_VOLUME,
            source_volume=SOURCE_VOLUME,
            protected_names=protected,
        )
        == "ok"
    )
    writable_archive = [
        {"Destination": "/var/lib/postgresql/data", "Name": RESTORE_VOLUME, "RW": True, "Type": "volume"},
        {"Destination": "/archive", "Name": ARCHIVE_VOLUME, "RW": True, "Type": "volume"},
    ]
    with pytest.raises(ProofError, match="does not match"):
        validate_recovered_mounts(
            writable_archive,
            restore_volume=RESTORE_VOLUME,
            archive_volume=ARCHIVE_VOLUME,
            source_volume=SOURCE_VOLUME,
            protected_names=protected,
        )


def test_recovery_target_rejects_unstructured_text():
    accepted = "2026-10-11 00:15:01.123456+0000"
    assert validate_target_timestamp(accepted) == accepted
    script = recovery_configuration(accepted)
    assert "recovery.signal" in script
    assert "/var/lib/postgresql/data/recovery.signal" in script
    assert SOURCE_NAME in SOURCE_BOOT
    assert "archive_mode=on" in SOURCE_BOOT
    assert SHARED_CONTAINER not in SOURCE_BOOT
    assert str(SHARED_PORT) not in SOURCE_BOOT
    with pytest.raises(ProofError, match="UTC timestamp"):
        recovery_configuration(
            "2026-10-11 00:15:01.123456+0000'; touch /tmp/pitr"
        )


def test_isolated_pitr_recovers_between_two_transactions(
    quiet_monitor,
    monkeypatch,
):
    if not _PITR:
        pytest.skip("SKAPE_PITR_DRILL is not set")
    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.fail("the PITR proof must run serially")
    if shutil.which("docker") is None:
        pytest.fail("docker is required for the PITR proof")
    for port in (SOURCE_PORT, RECOVERY_PORT):
        if not _port_is_free(port):
            pytest.fail(f"proof port {port} is already in use")

    resources = ProofResources()
    password = secrets.token_urlsafe(24)
    resources.password = password
    engines = []
    body_error = None
    app_name = f"skape_test_{secrets.token_hex(8)}"
    if not _DISPOSABLE_NAME.fullmatch(app_name):
        pytest.fail("refusing to generate an unsafe database name")
    try:
        _run_pitr_proof(
            resources,
            password,
            app_name,
            engines,
            monkeypatch,
        )
    except Exception as exc:
        body_error = exc
    finally:
        for engine in engines:
            engine.dispose()
        cleanup_errors = []
        try:
            cleanup_errors = resources.cleanup()
            if resources.captured:
                resources.shared_unchanged()
        except Exception as exc:
            cleanup_errors.append(_redact(exc, password))
    if body_error is not None:
        message = (
            f"{type(body_error).__name__}: {_redact(body_error, password)}"
        )
        if cleanup_errors:
            message = f"{message}; cleanup: {cleanup_errors}"
        pytest.fail(message[:2000])
    if cleanup_errors:
        pytest.fail(f"proof cleanup failed: {cleanup_errors}")
    leftover = _names("container") & {
        SOURCE_NAME,
        RECOVERED_NAME,
    }
    if leftover:
        pytest.fail("proof containers remained after cleanup")
    leftover_volumes = _names("volume") & {
        SOURCE_VOLUME,
        ARCHIVE_VOLUME,
        RESTORE_VOLUME,
    }
    if leftover_volumes:
        pytest.fail("proof volumes remained after cleanup")
    if NETWORK_NAME in _names("network"):
        pytest.fail("proof network remained after cleanup")


def _run_pitr_proof(resources, password, app_name, engines, monkeypatch):
    resources.capture()
    if SHARED_CONTAINER not in resources.snapshot["container"]:
        raise ProofError("shared test server was not found and will not be created")
    image_id = _docker(
        ["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE]
    ).strip()
    resources.create_network(NETWORK_NAME)
    resources.create_volume(SOURCE_VOLUME)
    resources.create_volume(ARCHIVE_VOLUME)
    resources.create_volume(RESTORE_VOLUME)
    source_id = _docker(
        [
            "docker",
            "run",
            "-d",
            "--pull",
            "never",
            "--name",
            SOURCE_NAME,
            "--network",
            NETWORK_NAME,
            "--label",
            f"skape.proof={PROOF_LABEL}",
            "-p",
            f"127.0.0.1:{SOURCE_PORT}:5432",
            "-e",
            f"POSTGRES_USER={ROLE_NAME}",
            "-e",
            f"POSTGRES_PASSWORD={password}",
            "-e",
            f"POSTGRES_DB={ADMIN_DATABASE}",
            "-v",
            f"{SOURCE_VOLUME}:/var/lib/postgresql/data",
            "-v",
            f"{ARCHIVE_VOLUME}:/var/lib/postgresql/archive",
            "-v",
            f"{RESTORE_VOLUME}:/var/lib/postgresql/restore",
            "--entrypoint",
            "bash",
            IMAGE,
            "-c",
            SOURCE_BOOT,
        ],
        password=password,
    ).strip()
    resources.own_container(SOURCE_NAME, source_id)
    validate_source_mounts(
        _mounts(SOURCE_NAME),
        data_volume=SOURCE_VOLUME,
        archive_volume=ARCHIVE_VOLUME,
        restore_volume=RESTORE_VOLUME,
        protected_names=resources.protected,
    )
    _wait_ready(SOURCE_NAME, ADMIN_DATABASE)
    _distinct_devices(SOURCE_NAME)
    settings = _psql(
        SOURCE_NAME,
        ADMIN_DATABASE,
        "SELECT current_setting('server_version_num') || '|' || "
        "current_setting('wal_level') || '|' || "
        "current_setting('archive_mode') || '|' || "
        "current_setting('cluster_name') || '|' || "
        "current_setting('data_directory')",
    )
    version, wal_level, archive_mode, cluster_name, data_directory = settings.split("|")
    if int(version) < 160000 or wal_level != "replica":
        raise ProofError("source server is not PostgreSQL 16 with wal_level replica")
    if archive_mode != "on" or cluster_name != SOURCE_NAME:
        raise ProofError("source archive settings are not the proof configuration")
    if data_directory != "/var/lib/postgresql/data":
        raise ProofError("source data directory is not the proof volume")
    source_image = _docker(
        ["docker", "inspect", "--format", "{{.Image}}", SOURCE_NAME]
    ).strip()
    if source_image != image_id:
        raise ProofError("source container is not the local postgres:16 image")

    current = _psql(
        SOURCE_NAME,
        ADMIN_DATABASE,
        "SELECT current_database()",
    )
    if current != ADMIN_DATABASE or not _DISPOSABLE_NAME.fullmatch(app_name):
        raise ProofError("refusing to create a database on an unexpected server")
    _psql(
        SOURCE_NAME,
        ADMIN_DATABASE,
        f'CREATE DATABASE "{app_name}"',
    )
    app_engine = _engine(password, SOURCE_PORT, app_name)
    engines.append(app_engine)
    app_url = app_engine.url.render_as_string(hide_password=False)
    parsed = make_url(app_url)
    if parsed.host != "127.0.0.1" or parsed.port != SOURCE_PORT:
        raise ProofError("refusing to migrate a database outside the proof source")
    if parsed.database != app_name:
        raise ProofError("refusing to migrate an unexpected database")
    module = _load_migrator()
    module._migrate(app_engine, app_url, app_name, "head")

    _bind(monkeypatch, app_engine)
    with TestClient(app) as api:
        _register(api, "pitr-owner-a@example.com", "PITR Org A")
        _register(api, "pitr-owner-b@example.com", "PITR Org B")
    with app_engine.connect() as connection:
        _assert_current(connection, app_name)
        organization_id = connection.execute(
            text("SELECT id FROM organizations WHERE name = :name"),
            {"name": "PITR Org A"},
        ).scalar()
        if organization_id is None:
            raise ProofError("synthetic organization was not created")
        stored = set(
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars()
        )
        if stored != set(expected_schema_revisions()):
            raise ProofError("source schema does not match the repository head")

    backup_started = time.perf_counter()
    _docker(
        [
            "docker",
            "exec",
            "-u",
            "postgres",
            SOURCE_NAME,
            "pg_basebackup",
            "-D",
            "/var/lib/postgresql/restore",
            "-h",
            "/var/run/postgresql",
            "-U",
            ROLE_NAME,
            "-X",
            "stream",
            "-c",
            "fast",
            "--no-password",
        ],
        timeout=180,
    )
    backup_seconds = time.perf_counter() - backup_started
    _docker(
        [
            "docker",
            "exec",
            SOURCE_NAME,
            "test",
            "-s",
            "/var/lib/postgresql/restore/PG_VERSION",
        ]
    )
    backup_bytes = _dir_bytes(SOURCE_NAME, "/var/lib/postgresql/restore")
    if backup_bytes <= 0:
        raise ProofError("base backup is empty")

    with app_engine.begin() as connection:
        _assert_current(connection, app_name)
        connection.execute(
            text(
                "INSERT INTO projects "
                "(name, description, status, organization_id) "
                "VALUES (:name, :description, 'active', :organization_id)"
            ),
            {
                "name": PROJECT_A,
                "description": "committed before the recovery target",
                "organization_id": organization_id,
            },
        )
    time.sleep(0.2)
    with app_engine.connect() as connection:
        _assert_current(connection, app_name)
        target = connection.execute(
            text(
                "SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC', "
                "'YYYY-MM-DD HH24:MI:SS.US') || '+0000'"
            )
        ).scalar()
    target = validate_target_timestamp(target)
    time.sleep(0.2)
    with app_engine.begin() as connection:
        _assert_current(connection, app_name)
        connection.execute(
            text(
                "INSERT INTO projects "
                "(name, description, status, organization_id) "
                "VALUES (:name, :description, 'active', :organization_id)"
            ),
            {
                "name": PROJECT_B,
                "description": "committed after the recovery target",
                "organization_id": organization_id,
            },
        )
    before_switch = _archive_names(SOURCE_NAME)
    _psql(SOURCE_NAME, app_name, "SELECT pg_switch_wal()")
    deadline = time.monotonic() + 45
    archived = set()
    while time.monotonic() < deadline:
        archived = _archive_names(SOURCE_NAME) - before_switch
        if archived:
            break
        time.sleep(0.5)
    if not archived:
        raise ProofError(
            "WAL archiving did not capture a segment after both transactions"
        )
    archive_bytes = _dir_bytes(SOURCE_NAME, "/var/lib/postgresql/archive")

    _docker(
        [
            "docker",
            "exec",
            SOURCE_NAME,
            "bash",
            "-c",
            recovery_configuration(target),
        ]
    )
    recovered_id = _docker(
        [
            "docker",
            "run",
            "-d",
            "--pull",
            "never",
            "--name",
            RECOVERED_NAME,
            "--network",
            NETWORK_NAME,
            "--label",
            f"skape.proof={PROOF_LABEL}",
            "-p",
            f"127.0.0.1:{RECOVERY_PORT}:5432",
            "-v",
            f"{RESTORE_VOLUME}:/var/lib/postgresql/data",
            "-v",
            f"{ARCHIVE_VOLUME}:/archive:ro",
            IMAGE,
            "postgres",
            "-c",
            "hot_standby=on",
            "-c",
            "timezone=UTC",
            "-c",
            f"cluster_name={RECOVERED_NAME}",
            "-c",
            "archive_mode=off",
        ]
    ).strip()
    resources.own_container(RECOVERED_NAME, recovered_id)
    validate_recovered_mounts(
        _mounts(RECOVERED_NAME),
        restore_volume=RESTORE_VOLUME,
        archive_volume=ARCHIVE_VOLUME,
        source_volume=SOURCE_VOLUME,
        protected_names=resources.protected,
    )
    replay_started = time.perf_counter()
    _wait_ready(RECOVERED_NAME, app_name)
    recovered = _engine(password, RECOVERY_PORT, app_name)
    engines.append(recovered)
    paused = False
    pause_deadline = time.monotonic() + 60
    while time.monotonic() < pause_deadline:
        with recovered.connect() as connection:
            _assert_current(connection, app_name)
            cluster, in_recovery, paused_replay = connection.execute(
                text(
                    "SELECT current_setting('cluster_name'), "
                    "pg_is_in_recovery(), pg_is_wal_replay_paused()"
                )
            ).one()
        if cluster != RECOVERED_NAME:
            raise ProofError("connected to an unexpected recovered cluster")
        if in_recovery and paused_replay:
            paused = True
            break
        time.sleep(0.5)
    if not paused:
        raise ProofError("recovered server did not pause at the recovery target")
    replay_seconds = time.perf_counter() - replay_started
    with recovered.connect() as connection:
        _assert_current(connection, app_name)
        names = connection.execute(
            text("SELECT name FROM projects ORDER BY name")
        ).scalars().all()
        revisions = set(
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars()
        )
        replay_at = connection.execute(
            text("SELECT pg_last_xact_replay_timestamp()")
        ).scalar()
    if names != [PROJECT_A]:
        raise ProofError(
            "recovered projects did not keep only the pre-target transaction"
        )
    if revisions != set(expected_schema_revisions()):
        raise ProofError("recovered schema does not match the repository head")
    if replay_at is None or replay_at.tzinfo is None:
        raise ProofError("recovery did not replay a timestamped transaction")
    replay_utc = replay_at.astimezone(timezone.utc)
    target_at = datetime.strptime(target, "%Y-%m-%d %H:%M:%S.%f%z")
    if replay_utc >= target_at:
        raise ProofError("replay timestamp is not before the recovery target")
    target_delta_seconds = (target_at - replay_utc).total_seconds()

    promote_started = time.perf_counter()
    with recovered.connect() as connection:
        autocommit = connection.execution_options(
            isolation_level="AUTOCOMMIT"
        )
        _assert_current(autocommit, app_name)
        promoted = autocommit.execute(
            text("SELECT pg_promote(true, 60)")
        ).scalar()
    if not promoted:
        raise ProofError("recovered server did not promote")
    with recovered.connect() as connection:
        in_recovery = connection.execute(
            text("SELECT pg_is_in_recovery()")
        ).scalar()
    if in_recovery:
        raise ProofError("recovered server stayed in recovery after promotion")
    promote_seconds = time.perf_counter() - promote_started

    _bind(monkeypatch, recovered)
    with TestClient(app) as api:
        owner_headers = _auth(api, "pitr-owner-a@example.com")
        outsider_headers = _auth(api, "pitr-owner-b@example.com")
        visible = api.get("/api/v1/projects/", headers=owner_headers)
        assert visible.status_code == 200
        assert [item["name"] for item in visible.json()] == [PROJECT_A]
        hidden = api.get("/api/v1/projects/", headers=outsider_headers)
        assert hidden.status_code == 200
        assert hidden.json() == []
        project_id = visible.json()[0]["id"]
        denied = api.get(
            f"/api/v1/projects/{project_id}",
            headers=outsider_headers,
        )
        assert denied.status_code == 404
        follow_up = api.post(
            "/api/v1/projects/",
            headers=owner_headers,
            json={
                "name": "PITR Follow-up",
                "description": "Created after promotion",
            },
        )
        assert follow_up.status_code == 200, follow_up.text
        monkeypatch.setenv("SKAPE_ENV", "production")
        ready = readiness(
            type(
                "Request",
                (),
                {
                    "state": type(
                        "State",
                        (),
                        {"request_id": "pitr-ready"},
                    )()
                },
            )()
        )
    assert ready["status"] == "ready"
    with recovered.connect() as connection:
        _assert_current(connection, app_name)
        recovered_names = connection.execute(
            text("SELECT name FROM projects ORDER BY name")
        ).scalars().all()
    if set(recovered_names) != {PROJECT_A, "PITR Follow-up"}:
        raise ProofError("promoted database did not accept the follow-up project")
    with app_engine.connect() as connection:
        _assert_current(connection, app_name)
        source_names = connection.execute(
            text("SELECT name FROM projects ORDER BY name")
        ).scalars().all()
        source_cluster = connection.execute(
            text("SELECT current_setting('cluster_name')")
        ).scalar()
    if set(source_names) != {PROJECT_A, PROJECT_B}:
        raise ProofError("source cluster changed during recovery")
    if source_cluster != SOURCE_NAME:
        raise ProofError("source cluster name changed")
    resources.shared_unchanged()
    total_seconds = time.perf_counter() - backup_started
    print(
        "pitr-proof "
        f"backup_seconds={backup_seconds:.6f} "
        f"replay_seconds={replay_seconds:.6f} "
        f"promote_seconds={promote_seconds:.6f} "
        f"total_seconds={total_seconds:.6f} "
        f"backup_bytes={backup_bytes} "
        f"archive_bytes={archive_bytes} "
        f"target={target} "
        f"replay_timestamp={replay_utc.strftime('%Y-%m-%d %H:%M:%S.%f+0000')} "
        f"target_delta_seconds={target_delta_seconds:.6f}",
        flush=True,
    )


def _load_migrator():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).with_name("test_device_monitor_postgres.py")
    spec = importlib.util.spec_from_file_location(
        "skape_pitr_migrator",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
