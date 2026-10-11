"""Build PostgreSQL client arguments without secrets.

Passwords and database URLs are not accepted as parameters. Connection
values that could carry them are rejected before an argument list is
returned. The child environment drops secret-bearing variables and
sets only a password-file path.

This module does not start ``pg_dump`` or ``pg_restore``. Timeout,
redaction, and process cleanup live in ``backup.runner``.
"""

import os
import re
import stat
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


def _platform_name():
    return os.name


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


def _sensitive_environment_name(key):
    upper = key.upper()
    if upper.startswith("PG") or upper in {
        "DATABASE_URL",
        "SKAPE_TEST_DATABASE_URL",
    }:
        return True
    return any(part in upper for part in _SECRET_NAME_PARTS)


def child_environment(base):
    """Copy of ``base`` without secret-bearing names or URL values."""

    if not isinstance(base, dict):
        _refuse()
    environment = {}
    for key, value in base.items():
        if not isinstance(key, str):
            _refuse()
        if _sensitive_environment_name(key):
            continue
        if not isinstance(value, str) or "://" in value:
            continue
        environment[key] = value
    environment.pop("PGPASSWORD", None)
    return environment


def _password_file_refused():
    raise BackupError("PostgreSQL password file is not safe")


def _path_has_parent_segment(path):
    parts = path.replace("\\", "/").split("/")
    if any(part in {".", ".."} for part in parts):
        return True
    empty_indexes = [index for index, part in enumerate(parts) if part == ""]
    if not empty_indexes:
        return False
    return empty_indexes != [0]


def _path_contains_symlink(path):
    current = Path(path)
    while True:
        try:
            linked = current.is_symlink()
        except OSError:
            return True
        if linked:
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def require_pgpassfile(path):
    """Return the normalized password-file path a client may use.

    The path must already be absolute. A relative path, a ``.`` or ``..``
    segment, a repeated separator, or a UNC path is rejected. The file
    and each of its parents must not be symlinks, and the target must be
    a regular file. On POSIX the mode must be ``0600``. On Windows
    (``os.name == "nt"``) those path and file-type checks still apply,
    but Unix mode ``0600`` cannot be verified and is not claimed. If any
    check cannot be completed, the path is rejected. The password is not
    read and is not included in an error.
    """

    if not isinstance(path, str) or not path or path.strip() != path:
        _password_file_refused()
    if (
        "://" in path
        or "\n" in path
        or "\r" in path
        or "\x00" in path
        or _path_has_parent_segment(path)
    ):
        _password_file_refused()
    selected = Path(path)
    if not selected.is_absolute():
        _password_file_refused()
    normalized = os.path.normpath(path)
    if (
        normalized.startswith("\\\\")
        or normalized.startswith("//")
        or _path_has_parent_segment(normalized)
        or not Path(normalized).is_absolute()
    ):
        _password_file_refused()
    if _path_contains_symlink(normalized):
        _password_file_refused()
    try:
        mode = os.lstat(normalized).st_mode
    except (OSError, AttributeError):
        _password_file_refused()
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        _password_file_refused()
    platform = _platform_name()
    if platform == "posix":
        if stat.S_IMODE(mode) != 0o600:
            _password_file_refused()
        return normalized
    if platform == "nt":
        return normalized
    _password_file_refused()


def postgres_child_environment(base, *, pgpassfile):
    """Environment for a PostgreSQL client.

    ``pgpassfile`` is checked by :func:`require_pgpassfile` and only the
    normalized path is stored. The password itself is not passed here.
    Secret-like variables and ``PG*`` variables from ``base`` are omitted
    so a parent URL or password cannot reach the client. ``PGPASSFILE``
    is set after those values are removed. On Windows the returned path
    has passed the path and regular-file checks; mode ``0600`` is not
    claimed there.
    """

    checked = require_pgpassfile(pgpassfile)
    environment = child_environment(base)
    environment["PGPASSFILE"] = checked
    environment.pop("PGPASSWORD", None)
    return environment


class PasswordFile:
    """Path of a password file and whether its mode is owner-only.

    ``permissions_guaranteed`` is true only on POSIX after mode ``0600``
    has been set and checked. On Windows it is false. A Windows caller
    must not treat the file as private because of this object.
    """

    def __init__(self, path, permissions_guaranteed):
        self.path = path
        self.permissions_guaranteed = permissions_guaranteed


def _same_open_file(fd, path):
    opened = os.fstat(fd)
    listed = os.lstat(path)
    if not opened.st_ino or not listed.st_ino:
        return False
    return opened.st_dev == listed.st_dev and opened.st_ino == listed.st_ino


def _pgpass_field(value):
    return value.replace("\\", "\\\\").replace(":", "\\:")


def write_password_file(path, *, host, port, user, database, password):
    """Create a PostgreSQL password file for one connection.

    The password is written only to this new file. On POSIX the file is
    created with mode ``0600`` and removed when that mode does not stick.
    On Windows (``os.name == "nt"``) the file is created without a Unix
    mode. Unix mode ``0600`` cannot be guaranteed there, and
    ``permissions_guaranteed`` is false. This function does not start a
    database client.
    """

    if not isinstance(password, str) or len(password) < 8 or len(password) > 256:
        _refuse()
    if "\n" in password or "\r" in password or "\x00" in password:
        _refuse()
    host, port_text, user, database = _require_endpoint(
        host, port, user, database
    )
    selected = Path(path)
    if (
        selected.is_symlink()
        or selected.parent.is_symlink()
        or not selected.parent.is_dir()
        or selected.name in {"", ".", ".."}
    ):
        raise BackupError("PostgreSQL password file could not be created")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(str(selected), flags, 0o600)
    except OSError:
        raise BackupError(
            "PostgreSQL password file could not be created"
        ) from None
    try:
        if selected.is_symlink() or not _same_open_file(descriptor, selected):
            raise BackupError("PostgreSQL password file could not be created")
        line = ":".join(
            (
                _pgpass_field(host),
                port_text,
                _pgpass_field(database),
                _pgpass_field(user),
                _pgpass_field(password),
            )
        )
        os.write(descriptor, (line + "\n").encode("utf-8"))
        os.fsync(descriptor)
    except BackupError:
        os.close(descriptor)
        selected.unlink(missing_ok=True)
        raise
    except OSError:
        os.close(descriptor)
        selected.unlink(missing_ok=True)
        raise BackupError(
            "PostgreSQL password file could not be created"
        ) from None
    os.close(descriptor)
    if _platform_name() == "posix":
        try:
            restrict_password_file(selected)
        except BackupError:
            selected.unlink(missing_ok=True)
            raise
        return PasswordFile(selected, True)
    if _platform_name() == "nt":
        return PasswordFile(selected, False)
    selected.unlink(missing_ok=True)
    raise BackupError(
        "PostgreSQL password file permissions are not supported on this platform"
    )


def restrict_password_file(path):
    """Limit a password file on Unix and refuse a mode that does not stick.

    On POSIX this sets mode ``0600`` and deletes that file when the mode
    does not stick. A symlink is rejected before ``chmod``, so the target
    of a link is left unchanged. On Windows (``os.name == "nt"``) this
    function returns without changing the file. Unix mode ``0600`` has
    not been demonstrated on Windows, and a Windows caller must not treat
    this return as proof that the file is owner-only. The password is
    still kept out of the client arguments. This function does not start
    a database client.
    """

    selected = Path(path)
    if selected.is_symlink():
        raise BackupError(
            "PostgreSQL password file permissions could not be restricted"
        )
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
