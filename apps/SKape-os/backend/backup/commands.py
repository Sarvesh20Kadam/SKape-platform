"""Build PostgreSQL client arguments without secrets.

Passwords and database URLs are not accepted as parameters. Connection
values that could carry them are rejected before an argument list is
returned. The child environment drops secret-bearing variables and
sets only a password-file path.

This module does not start ``pg_dump`` or ``pg_restore``. A subprocess
timeout, stderr redaction, and client-process cleanup are not provided
here; they belong to a runner that starts the client and tests those
protections.
"""

import os
import re
from pathlib import Path

from backup.errors import BackupError


_NAME = r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,62}"
_HOST = r"[A-Za-z0-9][A-Za-z0-9.-]{0,253}"
_SECRET_NAME_PARTS = (
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "ACCESS_KEY",
    "AUTHORIZATION",
    "CREDENTIAL",
    "API_KEY",
    "PRIVATE_KEY",
    "SIGNING",
    "SESSION",
)
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/].+")


def _refuse():
    raise BackupError("PostgreSQL command is not safe")


def _tool_basename(executable):
    return executable.replace("\\", "/").rsplit("/", 1)[-1]


def _absolute_executable(executable):
    if os.path.isabs(executable):
        return True
    if _WINDOWS_ABSOLUTE.fullmatch(executable):
        return True
    return executable.startswith("\\\\") or executable.startswith("//")


def _require_tool(executable, expected):
    """Accept a bare client name or an absolute path to that client.

    A relative path is rejected. The basename must be the expected
    client, with an optional ``.exe`` suffix.
    """

    if not isinstance(executable, str) or executable.strip() != executable:
        _refuse()
    if not executable or any(character in executable for character in "\n\r\x00"):
        _refuse()
    if "://" in executable:
        _refuse()
    normalized = executable.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        _refuse()
    name = _tool_basename(executable).lower()
    if name not in {expected, expected + ".exe"}:
        _refuse()
    bare = "/" not in normalized
    if bare:
        return executable
    if not _absolute_executable(executable):
        _refuse()
    return executable


def _require_text(value, pattern):
    if (
        not isinstance(value, str)
        or "://" in value
        or any(character.isspace() for character in value)
        or not re.fullmatch(pattern, value)
    ):
        _refuse()
    return value


def _require_endpoint(host, port, user, database):
    if isinstance(port, bool) or not isinstance(port, int):
        _refuse()
    if port < 1 or port > 65535:
        _refuse()
    return (
        _require_text(host, _HOST),
        str(port),
        _require_text(user, _NAME),
        _require_text(database, _NAME),
    )


def _assert_argv_safe(argv):
    for argument in argv:
        if not isinstance(argument, str) or "://" in argument:
            _refuse()
        if argument.startswith("--password") or argument == "-W":
            _refuse()
    return argv


def dump_argv(executable, *, host, port, user, database):
    """Arguments for one custom-format ``pg_dump``."""

    tool = _require_tool(executable, "pg_dump")
    host, port_text, user, database = _require_endpoint(
        host, port, user, database
    )
    return _assert_argv_safe(
        [
            tool,
            "-Fc",
            "--no-owner",
            "--no-acl",
            "-h",
            host,
            "-p",
            port_text,
            "-U",
            user,
            "-d",
            database,
        ]
    )


def restore_argv(executable, *, host, port, user, database):
    """Arguments for ``pg_restore`` into an existing empty database.

    The argument list does not include ``--clean``. Selecting the empty
    target database remains the caller's responsibility.
    """

    tool = _require_tool(executable, "pg_restore")
    host, port_text, user, database = _require_endpoint(
        host, port, user, database
    )
    return _assert_argv_safe(
        [
            tool,
            "--no-owner",
            "--exit-on-error",
            "--single-transaction",
            "-h",
            host,
            "-p",
            port_text,
            "-U",
            user,
            "-d",
            database,
        ]
    )


def postgres_child_environment(base, *, pgpassfile):
    """Environment for a PostgreSQL client.

    ``pgpassfile`` is a path. The password itself is not passed here.
    Secret-like variables and ``PG*`` variables from ``base`` are omitted
    so a parent URL or password cannot reach the client.
    """

    if not isinstance(pgpassfile, str) or not pgpassfile.strip():
        _refuse()
    if "://" in pgpassfile or "\n" in pgpassfile or "\x00" in pgpassfile:
        _refuse()
    if not isinstance(base, dict):
        _refuse()
    environment = {}
    for key, value in base.items():
        if not isinstance(key, str):
            _refuse()
        upper = key.upper()
        if upper.startswith("PG"):
            continue
        if upper in {"DATABASE_URL", "SKAPE_TEST_DATABASE_URL"}:
            continue
        if any(part in upper for part in _SECRET_NAME_PARTS):
            continue
        if not isinstance(value, str) or "://" in value:
            continue
        environment[key] = value
    environment["PGPASSFILE"] = pgpassfile
    environment.pop("PGPASSWORD", None)
    return environment


def restrict_password_file(path):
    """Limit a password file on Unix and refuse a mode that does not stick.

    On POSIX this sets mode ``0600`` and deletes the file when that mode
    does not stick. On Windows (``os.name == "nt"``) this function
    returns without changing the file. Unix mode ``0600`` has not been
    demonstrated on Windows, and a Windows caller must not treat this
    return as proof that the file is owner-only. The password is still
    kept out of the client arguments. This function does not start a
    database client.
    """

    selected = Path(path)
    if os.name == "posix":
        os.chmod(selected, 0o600)
        mode = os.stat(selected).st_mode & 0o777
        if mode != 0o600:
            selected.unlink(missing_ok=True)
            raise BackupError(
                "PostgreSQL password file permissions could not be restricted"
            )
        return
    if os.name == "nt":
        return
    selected.unlink(missing_ok=True)
    raise BackupError(
        "PostgreSQL password file permissions are not supported on this platform"
    )
