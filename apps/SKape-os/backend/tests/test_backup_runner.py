"""Offline checks for backup process execution.

These tests do not connect to PostgreSQL and do not run pg_dump or
pg_restore. A local Python process is used only to prove timeout and
cleanup behavior.
"""

import io
import io
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import backup.runner as runner_module
from backup.commands import write_password_file
from backup.errors import BackupError
from backup.runner import run_postgres_client, run_process


PASSWORD = "secret-password"
URL = "postgresql://reader:secret-password@db.internal/skape"


class FakeProcess:
    def __init__(self, *, stdout=b"", stderr=b"", code=0, timeout=False):
        self.pid = 12345
        self.returncode = None
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self._code = code
        self._timeout = timeout
        self.stopped = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self._timeout and self.returncode is None:
            raise subprocess.TimeoutExpired("hidden-command", timeout or 1)
        if self.returncode is None:
            self.returncode = self._code
        return self.returncode

    def kill(self):
        self.stopped = True
        self.returncode = -9


def _spawn(process):
    def spawn(argv, env, stdout):
        process.seen = {"argv": argv, "env": env, "stdout": stdout}
        return process

    return spawn


def _local_env():
    environment = {}
    for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"):
        value = os.environ.get(key)
        if isinstance(value, str) and "://" not in value:
            environment[key] = value
    return environment


def test_timeout_message_omits_the_command_and_stops_the_process(monkeypatch):
    process = FakeProcess(timeout=True)
    stopped = {}

    def stop(target):
        target.stopped = True
        target.returncode = -9
        stopped["process"] = target

    monkeypatch.setattr(runner_module, "_stop_process", stop)
    with pytest.raises(BackupError, match="timed out after 1 second") as caught:
        run_process(
            ["pg_dump", "-Fc"],
            env={"PATH": "C:\\PostgreSQL\\16\\bin"},
            timeout=1,
            spawn=_spawn(process),
        )
    assert stopped["process"] is process
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "hidden-command" not in str(caught.value)
    assert "pg_dump" not in str(caught.value)


def test_failed_command_redacts_urls_and_secrets():
    process = FakeProcess(
        stderr=f"{URL}\npassword={PASSWORD}\n".encode("utf-8"),
        code=2,
    )
    with pytest.raises(BackupError, match="PostgreSQL client failed") as caught:
        run_process(
            ["pg_dump", "-Fc"],
            env={"PATH": "C:\\PostgreSQL\\16\\bin"},
            timeout=5,
            redact_secrets=(PASSWORD,),
            spawn=_spawn(process),
        )
    message = str(caught.value)
    assert "postgresql://" not in message
    assert PASSWORD not in message
    assert "db.internal" not in message
    assert "[redacted-url]" in message
    assert "password=[redacted]" in message


def test_unsafe_environment_is_rejected_before_spawn():
    def spawn(argv, env, stdout):
        raise AssertionError("client was started")

    with pytest.raises(BackupError, match="environment is not safe"):
        run_process(
            ["pg_dump", "-Fc"],
            env={
                "PATH": "C:\\PostgreSQL\\16\\bin",
                "AUTHORIZATION": "Bearer auth-value",
                "DATABASE_URL": URL,
            },
            timeout=5,
            spawn=spawn,
        )


def test_database_url_argument_is_rejected_before_spawn():
    def spawn(argv, env, stdout):
        raise AssertionError("client was started")

    with pytest.raises(BackupError, match="command is not safe"):
        run_process(
            ["pg_dump", URL],
            env={"PATH": "C:\\PostgreSQL\\16\\bin"},
            timeout=5,
            spawn=spawn,
        )


def test_postgres_client_rejects_an_unexpected_executable():
    with pytest.raises(BackupError, match="command is not safe"):
        run_postgres_client(
            [sys.executable, "-c", "import sys; sys.exit(0)"],
            env=_local_env(),
            timeout=5,
        )


def test_short_redaction_secret_is_rejected():
    with pytest.raises(BackupError, match="cannot be redacted"):
        run_process(
            ["pg_dump"],
            env={"PATH": "C:\\PostgreSQL\\16\\bin"},
            timeout=5,
            redact_secrets=("short",),
            spawn=_spawn(FakeProcess()),
        )


def test_timeout_stops_a_local_python_process():
    started = time.monotonic()
    with pytest.raises(BackupError, match="timed out after 1 second"):
        run_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            env=_local_env(),
            timeout=1,
        )
    assert time.monotonic() - started < 10


def test_failed_local_command_removes_partial_stdout(tmp_path):
    output = tmp_path / "client-out.bin"
    with pytest.raises(BackupError, match="PostgreSQL client failed"):
        run_process(
            [sys.executable, "-c", "import sys; sys.exit(4)"],
            env=_local_env(),
            timeout=30,
            stdout_path=output,
        )
    assert not output.exists()


def test_local_stdout_is_written_without_returning_stderr_bytes(tmp_path):
    output = tmp_path / "client-out.bin"
    result = run_process(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'PGDMPsample')",
        ],
        env=_local_env(),
        timeout=30,
        stdout_path=output,
    )
    assert result.returncode == 0
    assert result.stdout_size == len(b"PGDMPsample")
    assert output.read_bytes() == b"PGDMPsample"
    assert result.stderr_text == ""


def test_password_file_records_mode_and_platform_guarantee(tmp_path, monkeypatch):
    recorded = {}
    real_open = os.open

    def tracking_open(path, flags, mode=0o777, **kwargs):
        recorded["mode"] = mode
        return real_open(path, flags, mode)

    monkeypatch.setattr(os, "open", tracking_open)
    created = write_password_file(
        tmp_path / "pgpass",
        host="db.internal",
        port=5432,
        user="reader",
        database="skape",
        password=PASSWORD,
    )
    assert recorded["mode"] == 0o600
    assert created.permissions_guaranteed is (os.name == "posix")
    text = Path(created.path).read_text(encoding="utf-8")
    assert text == f"db.internal:5432:skape:reader:{PASSWORD}\n"


def test_posix_password_file_checks_owner_only_mode(tmp_path, monkeypatch):
    monkeypatch.setattr("backup.commands._platform_name", lambda: "posix")
    checked = {}

    def restrict(path):
        checked["path"] = path

    monkeypatch.setattr("backup.commands.restrict_password_file", restrict)
    created = write_password_file(
        tmp_path / "pgpass",
        host="db.internal",
        port=5432,
        user="reader",
        database="skape",
        password="secret:password",
    )
    assert created.permissions_guaranteed is True
    assert checked["path"] == created.path
    text = Path(created.path).read_text(encoding="utf-8")
    assert "secret\\:password" in text


def test_password_file_symlink_is_rejected(tmp_path, monkeypatch):
    target = tmp_path / "pgpass"
    monkeypatch.setattr(Path, "is_symlink", lambda self: self == target)
    with pytest.raises(BackupError, match="could not be created"):
        write_password_file(
            target,
            host="db.internal",
            port=5432,
            user="reader",
            database="skape",
            password=PASSWORD,
        )
    assert not target.exists()


def _rendered_failure(stderr):
    process = FakeProcess(stderr=stderr, code=2)
    with pytest.raises(BackupError, match="PostgreSQL client failed") as caught:
        run_process(
            ["pg_dump", "-Fc"],
            env={"PATH": r"C:\PostgreSQL\16\bin"},
            timeout=5,
            redact_secrets=(PASSWORD,),
            spawn=_spawn(process),
        )
    return caught.value


def _cause_text(error):
    parts = []
    current = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(str(current))
        current = current.__cause__
    return "\n".join(parts)


def test_environment_assignments_are_redacted_in_errors_and_causes():
    secret = "synthetic-password-value"
    stderr = (
        "PGPASSWORD=synthetic-password-value\n"
        "pgpassfile=/tmp/synthetic-password-value\n"
        'PgPassFile="synthetic-password-value"\n'
        "AWS_SECRET_ACCESS_KEY=synthetic-password-value\n"
        "DATABASE_URL=postgresql://reader:synthetic-password-value@db.internal/skape\n"
        "PGHOST=db.internal\n"
    ).encode("utf-8")
    error = _rendered_failure(stderr)
    rendered = _cause_text(error)
    assert secret not in rendered
    assert secret not in str(error.__context__)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "PGPASSWORD=[redacted]" in str(error)
    assert "pgpassfile=[redacted]" in str(error)
    assert "PgPassFile=[redacted]" in str(error)
    assert "AWS_SECRET_ACCESS_KEY=[redacted]" in str(error)
    assert "db.internal" not in str(error).split("PGHOST=", 1)[0]
    assert "PGHOST=db.internal" in str(error)


def test_environment_assignments_are_redacted_in_success_stderr():
    process = FakeProcess(
        stderr=b"notice PGPASSWORD=synthetic-password-value\n",
        code=0,
    )
    result = run_process(
        ["pg_dump", "-Fc"],
        env={"PATH": r"C:\PostgreSQL\16\bin"},
        timeout=5,
        spawn=_spawn(process),
    )
    assert "synthetic-password-value" not in result.stderr_text
    assert "PGPASSWORD=[redacted]" in result.stderr_text


def test_relative_pgpassfile_is_rejected_before_spawn(tmp_path):
    def spawn(argv, env, stdout):
        raise AssertionError("client was started")

    candidates = (
        "pgpass",
        str(tmp_path / ".." / "pgpass"),
    )
    for candidate in candidates:
        with pytest.raises(BackupError, match="password file is not safe"):
            run_process(
                ["pg_dump", "-Fc"],
                env={
                    "PATH": r"C:\PostgreSQL\16\bin",
                    "PGPASSFILE": candidate,
                },
                timeout=5,
                spawn=spawn,
            )


def test_absolute_regular_pgpassfile_is_passed_to_the_child(tmp_path):
    target = tmp_path / "pgpass"
    target.write_text("unused\n", encoding="utf-8")
    seen = {}

    def spawn(argv, env, stdout):
        seen["env"] = env
        return FakeProcess()

    run_process(
        ["pg_dump", "-Fc"],
        env={
            "PATH": r"C:\PostgreSQL\16\bin",
            "PGPASSFILE": str(target),
        },
        timeout=5,
        spawn=spawn,
    )
    assert seen["env"]["PGPASSFILE"] == os.path.normpath(str(target))
    assert "PGPASSWORD" not in seen["env"]


def test_missing_executable_removes_the_stdout_file(tmp_path):
    output = tmp_path / "client-out.bin"
    missing = tmp_path / "missing-tool"
    with pytest.raises(BackupError, match="could not be started") as caught:
        run_process(
            [str(missing)],
            env=_local_env(),
            timeout=5,
            stdout_path=output,
        )
    assert not output.exists()
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert missing.name not in str(caught.value)


def test_excessive_stderr_stops_the_child_without_returning_output():
    secret = "synthetic-password-value"
    script = (
        "import sys, time; "
        "sys.stderr.buffer.write(b'PGPASSWORD=synthetic-password-value\\n'); "
        "sys.stderr.buffer.write(b'A' * 70000); "
        "sys.stderr.buffer.write(b'PGPASSWORD=synthetic-password-value\\n'); "
        "sys.stderr.flush(); "
        "time.sleep(30)"
    )
    started = time.monotonic()
    with pytest.raises(
        BackupError,
        match="exceeded the diagnostic limit",
    ) as caught:
        run_process(
            [sys.executable, "-c", script],
            env=_local_env(),
            timeout=30,
        )
    assert time.monotonic() - started < 10
    message = str(caught.value)
    assert secret not in message
    assert "A" * 80 not in message
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_cleanup_failure_does_not_claim_the_client_stopped(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 1),
    )
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None, raising=False)

    class Stuck(FakeProcess):
        def poll(self):
            return None

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired("hidden-command", timeout or 1)

        def kill(self):
            self.stopped = True

    with pytest.raises(BackupError, match="could not be stopped") as caught:
        runner_module._stop_process(Stuck())
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert "hidden-command" not in str(caught.value)
    assert "12345" not in str(caught.value)


def test_ordinary_cleanup_returns_after_the_client_exits(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0),
    )
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None, raising=False)
    process = FakeProcess()
    runner_module._stop_process(process)
    assert process.poll() is not None


def test_timeout_surfaces_cleanup_failure(monkeypatch):
    def stop(process):
        raise BackupError("PostgreSQL client could not be stopped")

    monkeypatch.setattr(runner_module, "_stop_process", stop)
    with pytest.raises(BackupError, match="could not be stopped") as caught:
        run_process(
            ["pg_dump", "-Fc"],
            env={"PATH": r"C:\PostgreSQL\16\bin"},
            timeout=1,
            spawn=_spawn(FakeProcess(timeout=True)),
        )
    assert "timed out" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
