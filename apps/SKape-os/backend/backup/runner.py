"""Run a PostgreSQL client with a finite timeout and redacted errors.

The runner does not open a database connection itself. It starts the
argument vector it is given. ``run_postgres_client`` accepts only
``pg_dump`` and ``pg_restore``. ``run_process`` is the shared execution
primitive used by that wrapper and by offline tests.

On POSIX the child is placed in a new session and the session is killed
after a timeout. On Windows the child is started in a new process group
and ``taskkill /F /T`` stops that process tree. Stderr is retained only
up to 64 KiB while it is read. A larger stream stops the client and
raises ``BackupError`` without that output. If the client cannot be
shown to have exited, the runner raises a cleanup error instead of
reporting success. Neither path returns the command line, the
environment, or raw stderr to the caller.
"""

import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path

from backup.commands import _sensitive_environment_name, require_pgpassfile
from backup.errors import BackupError


DEFAULT_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 600
_STDERR_LIMIT = 65536
_CLIENT_NAMES = {"pg_dump", "pg_dump.exe", "pg_restore", "pg_restore.exe"}
_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+")
_ASSIGNMENT_NAME = (
    "password|passwd|pgpassfile|secret|token|access_key|authorization|"
    "credential|api_key|private_key|signing|session|database_url"
)
_ASSIGNMENT = re.compile(
    r"(?i)(?<![A-Za-z0-9_])"
    r"([A-Za-z0-9_]*(?:" + _ASSIGNMENT_NAME + r")[A-Za-z0-9_]*)"
    r"""\s*[:=]\s*(?:"[^"\r\n]*"|'[^'\r\n]*'|\S+)"""
)


class ClientResult:
    """Success result. ``stderr_text`` has already been redacted."""

    def __init__(self, returncode, stdout_size, stderr_text):
        self.returncode = returncode
        self.stdout_size = stdout_size
        self.stderr_text = stderr_text


def require_timeout(timeout):
    """Accept a whole number of seconds from 1 through 600."""

    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise BackupError("PostgreSQL client timeout is invalid")
    if timeout < 1 or timeout > MAX_TIMEOUT_SECONDS:
        raise BackupError("PostgreSQL client timeout is invalid")
    return timeout


def redact_output(payload, secrets):
    """Remove URLs, secret assignments, and caller-supplied literals."""

    if isinstance(payload, (bytes, bytearray)):
        text = bytes(payload).decode("utf-8", errors="replace")
    elif isinstance(payload, str):
        text = payload
    else:
        raise BackupError("PostgreSQL client output cannot be redacted")
    text = _URL.sub("[redacted-url]", text)
    text = _ASSIGNMENT.sub(lambda match: match.group(1) + "=[redacted]", text)
    for secret in secrets:
        text = text.replace(secret, "[redacted]")
    if len(text) > _STDERR_LIMIT:
        text = text[:_STDERR_LIMIT] + "[truncated]"
    return text.strip()


def _require_secrets(secrets):
    if secrets is None:
        return ()
    if not isinstance(secrets, (list, tuple)):
        raise BackupError("PostgreSQL client output cannot be redacted")
    cleaned = []
    for secret in secrets:
        if not isinstance(secret, str) or len(secret) < 8:
            raise BackupError("PostgreSQL client output cannot be redacted")
        if "\n" in secret or "\r" in secret or "\x00" in secret:
            raise BackupError("PostgreSQL client output cannot be redacted")
        cleaned.append(secret)
    return tuple(cleaned)


def _require_argv(argv):
    if not isinstance(argv, (list, tuple)) or not argv:
        raise BackupError("PostgreSQL command is not safe")
    cleaned = []
    for argument in argv:
        if not isinstance(argument, str) or argument.strip() != argument:
            raise BackupError("PostgreSQL command is not safe")
        if (
            not argument
            or "://" in argument
            or "\n" in argument
            or "\r" in argument
            or "\x00" in argument
        ):
            raise BackupError("PostgreSQL command is not safe")
        if argument.startswith("--password") or argument == "-W":
            raise BackupError("PostgreSQL command is not safe")
        cleaned.append(argument)
    return cleaned


def _require_environment(environment):
    if not isinstance(environment, dict):
        raise BackupError("PostgreSQL client environment is not safe")
    safe = {}
    for key, value in environment.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise BackupError("PostgreSQL client environment is not safe")
        if key.upper() == "PGPASSFILE":
            if key != "PGPASSFILE" or "PGPASSFILE" in safe:
                raise BackupError("PostgreSQL client environment is not safe")
            safe["PGPASSFILE"] = require_pgpassfile(value)
            continue
        if _sensitive_environment_name(key):
            raise BackupError("PostgreSQL client environment is not safe")
        if "://" in value or "\n" in value or "\x00" in value:
            raise BackupError("PostgreSQL client environment is not safe")
        safe[key] = value
    safe.pop("PGPASSWORD", None)
    return safe


def _client_name(executable):
    return executable.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _same_open_file(fd, path):
    opened = os.fstat(fd)
    listed = os.lstat(path)
    if not opened.st_ino or not listed.st_ino:
        return False
    return opened.st_dev == listed.st_dev and opened.st_ino == listed.st_ino


def _open_stdout(path):
    selected = Path(path)
    if (
        selected.is_symlink()
        or selected.parent.is_symlink()
        or not selected.parent.is_dir()
        or selected.name in {"", ".", ".."}
    ):
        raise BackupError("PostgreSQL client output could not be created")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = None
    try:
        descriptor = os.open(str(selected), flags, 0o600)
    except OSError:
        descriptor = None
    if descriptor is None:
        raise BackupError("PostgreSQL client output could not be created")
    try:
        if selected.is_symlink() or not _same_open_file(descriptor, selected):
            raise BackupError("PostgreSQL client output could not be created")
    except BackupError:
        os.close(descriptor)
        selected.unlink(missing_ok=True)
        raise
    return descriptor


def _drop_stdout(handle, path):
    if handle is not None:
        try:
            handle.close()
        except OSError:
            pass
    if path is None:
        return
    failed = False
    try:
        os.unlink(path)
    except FileNotFoundError:
        return
    except OSError:
        failed = True
    if failed:
        raise BackupError("PostgreSQL client output could not be created")


def _popen(argv, env, stdout):
    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": stdout,
        "stderr": subprocess.PIPE,
        "env": env,
        "close_fds": True,
    }
    if os.name == "posix":
        kwargs["start_new_session"] = True
    elif os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(argv, **kwargs)


def _signal_tree(process):
    pid = getattr(process, "pid", None)
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        try:
            process.kill()
        except OSError:
            pass
        return
    if os.name == "posix":
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            try:
                process.kill()
            except OSError:
                pass
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            process.kill()
        except OSError:
            pass
        return
    try:
        process.kill()
    except OSError:
        pass


def _wait_for_exit(process, seconds):
    try:
        process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        return False
    return process.poll() is not None


def _stop_process(process):
    """Stop a client and require the process to actually exit."""

    if process.poll() is not None:
        return
    _signal_tree(process)
    if _wait_for_exit(process, 5):
        return
    _signal_tree(process)
    if _wait_for_exit(process, 5):
        return
    raise BackupError("PostgreSQL client could not be stopped")


def _consume_stderr(stream, state):
    if stream is None:
        return
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                return
            if state["overflow"]:
                continue
            room = _STDERR_LIMIT - len(state["data"])
            if len(chunk) <= room:
                state["data"].extend(chunk)
                continue
            if room > 0:
                state["data"].extend(chunk[:room])
            state["overflow"] = True
    except Exception:
        state["failed"] = True


def _consume_stdout(stream, state):
    if stream is None:
        return
    try:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return
            state["size"] += len(chunk)
    except Exception:
        state["failed"] = True


def _join_capture(threads):
    alive = False
    for thread in threads:
        thread.join(timeout=5)
        if thread.is_alive():
            alive = True
    return not alive


def _clear_captured_stderr(state):
    state["data"].clear()


def _finish(process, timeout, secrets):
    stderr_state = {"data": bytearray(), "overflow": False, "failed": False}
    stdout_state = {"size": 0, "failed": False}
    threads = (
        threading.Thread(
            target=_consume_stderr,
            args=(process.stderr, stderr_state),
            daemon=True,
        ),
        threading.Thread(
            target=_consume_stdout,
            args=(process.stdout, stdout_state),
            daemon=True,
        ),
    )
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    timed_out = False
    while process.poll() is None:
        if stderr_state["overflow"] or stderr_state["failed"]:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        try:
            process.wait(timeout=min(0.05, remaining))
        except subprocess.TimeoutExpired:
            time.sleep(0.01)
    if stderr_state["overflow"] or stderr_state["failed"]:
        _stop_process(process)
        _join_capture(threads)
        _clear_captured_stderr(stderr_state)
        if stderr_state["failed"] and not stderr_state["overflow"]:
            raise BackupError("PostgreSQL client output cannot be redacted")
        raise BackupError(
            "PostgreSQL client output exceeded the diagnostic limit"
        )
    if timed_out or process.poll() is None:
        _stop_process(process)
        _join_capture(threads)
        _clear_captured_stderr(stderr_state)
        raise BackupError(
            f"PostgreSQL client timed out after {timeout} seconds"
        )
    if not _join_capture(threads):
        _stop_process(process)
        _clear_captured_stderr(stderr_state)
        raise BackupError("PostgreSQL client could not be stopped")
    if stderr_state["failed"] or stdout_state["failed"]:
        _clear_captured_stderr(stderr_state)
        raise BackupError("PostgreSQL client output cannot be redacted")
    if stderr_state["overflow"]:
        _clear_captured_stderr(stderr_state)
        raise BackupError(
            "PostgreSQL client output exceeded the diagnostic limit"
        )
    redacted = redact_output(bytes(stderr_state["data"]), secrets)
    _clear_captured_stderr(stderr_state)
    returncode = process.returncode
    if returncode != 0:
        message = "PostgreSQL client failed"
        if redacted:
            message = message + ": " + redacted
        raise BackupError(message)
    return ClientResult(returncode, stdout_state["size"], redacted)


def run_process(
    argv,
    *,
    env,
    timeout,
    redact_secrets=(),
    stdout_path=None,
    spawn=None,
):
    """Run ``argv`` and return only redacted success data.

    Raw stderr is not returned. A nonzero status, a timeout, an output
    limit, or a cleanup failure raises ``BackupError``. Those messages
    do not include the argument vector or unredacted stderr.
    """

    cleaned = _require_argv(argv)
    safe_env = _require_environment(env)
    seconds = require_timeout(timeout)
    secrets = _require_secrets(redact_secrets)
    starter = spawn or _popen
    stdout_handle = None
    try:
        if stdout_path is None:
            stdout_arg = subprocess.PIPE
        else:
            stdout_handle = os.fdopen(_open_stdout(stdout_path), "wb")
            stdout_arg = stdout_handle
        start_failed = False
        try:
            process = starter(cleaned, safe_env, stdout_arg)
        except OSError:
            start_failed = True
        if start_failed:
            handle = stdout_handle
            stdout_handle = None
            _drop_stdout(handle, stdout_path)
            raise BackupError("PostgreSQL client could not be started")
        try:
            result = _finish(process, seconds, secrets)
        except BackupError:
            handle = stdout_handle
            stdout_handle = None
            try:
                _drop_stdout(handle, stdout_path)
            except BackupError:
                pass
            raise
    finally:
        if stdout_handle is not None:
            stdout_handle.close()
    if stdout_path is not None:
        size_failed = False
        try:
            result.stdout_size = os.path.getsize(stdout_path)
        except OSError:
            size_failed = True
        if size_failed:
            raise BackupError("PostgreSQL client output could not be created")
    return result


def run_postgres_client(
    argv,
    *,
    env,
    timeout,
    redact_secrets=(),
    stdout_path=None,
    spawn=None,
):
    """Run one ``pg_dump`` or ``pg_restore`` argument vector."""

    if not isinstance(argv, (list, tuple)) or not argv or not isinstance(argv[0], str):
        raise BackupError("PostgreSQL command is not safe")
    if _client_name(argv[0]) not in _CLIENT_NAMES:
        raise BackupError("PostgreSQL command is not safe")
    return run_process(
        argv,
        env=env,
        timeout=timeout,
        redact_secrets=redact_secrets,
        stdout_path=stdout_path,
        spawn=spawn,
    )
