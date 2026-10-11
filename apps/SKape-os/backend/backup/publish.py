"""Publish ``latest.json`` only after the dump matches a verified manifest.

A failed check leaves an existing ``latest.json`` unchanged. This phase
does not upload the dump or contact object storage.

Local publishers share an exclusive lock file in the validated backup
directory. Under that lock the publisher reads ``latest.json`` again and
replaces it only when the new manifest is strictly newer than the
current verified backup. An equal timestamp is published again only when
the canonical manifest text is unchanged; a different backup at that
same timestamp is refused. ``os.replace`` then swaps a fully written
temporary file in the same directory, so a local reader sees the
previous file or the complete replacement.

The lock and the replace apply only to this local directory. They do
not coordinate writers on another machine or in object storage. A future
R2 publication must use its own conditional write for the remote
``latest.json`` and must not treat this lock file as a bucket lock.
"""

import os
import tempfile
import time
from pathlib import Path

from backup.dump import require_dump_checksum
from backup.errors import BackupError
from backup.manifest import parse_manifest, serialize_manifest, validate_manifest


_DIRECTORY_PREFIX = "skape-backup-"
_LATEST_NAME = "latest.json"
_LOCK_NAME = ".publish.lock"
LOCK_WAIT_SECONDS = 5.0


def require_backup_directory(directory):
    """Accept a real backup directory and reject a symlink or other path."""

    path = Path(directory)
    if (
        path.is_symlink()
        or not path.is_dir()
        or not path.name.startswith(_DIRECTORY_PREFIX)
    ):
        raise BackupError("refusing to publish outside a backup directory")
    resolved = path.resolve()
    if resolved.name != path.name or resolved.is_symlink():
        raise BackupError("refusing to publish outside a backup directory")
    return resolved


def _lock_descriptor(fd):
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        if os.fstat(fd).st_size < 1:
            os.write(fd, b"\0")
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        return
    if os.name == "posix":
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    raise BackupError("backup publication is not supported on this platform")


def _unlock_descriptor(fd):
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return
    if os.name == "posix":
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def acquire_publication_lock(directory):
    """Lock one local backup directory.

    The lock is an advisory file lock on this computer. It is not an
    object-storage lock. A publisher that cannot obtain it within
    ``LOCK_WAIT_SECONDS`` fails closed.
    """

    selected = require_backup_directory(directory)
    lock_path = selected / _LOCK_NAME
    if lock_path.is_symlink():
        raise BackupError("refusing to publish outside a backup directory")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        try:
            _lock_descriptor(fd)
            return fd
        except BackupError:
            os.close(fd)
            raise
        except OSError:
            if time.monotonic() >= deadline:
                os.close(fd)
                raise BackupError(
                    "backup publication is already in progress"
                ) from None
            time.sleep(0.02)


def release_publication_lock(fd):
    """Release a lock acquired by :func:`acquire_publication_lock`."""

    try:
        _unlock_descriptor(fd)
    except OSError:
        pass
    os.close(fd)


def _read_verified_pointer(path, *, expected_revisions, now):
    if path.is_symlink():
        raise BackupError("refusing to publish through a symlink")
    if not path.exists():
        return None
    if not path.is_file():
        raise BackupError("refusing to publish outside a backup directory")
    try:
        current = parse_manifest(
            path.read_text(encoding="utf-8"),
            expected_revisions=expected_revisions,
            now=now,
        )
    except BackupError:
        raise BackupError(
            "refusing to replace an unverified backup pointer"
        ) from None
    if not current.verified:
        raise BackupError("refusing to replace an unverified backup pointer")
    return current


def _same_manifest(left, right):
    return serialize_manifest(left) == serialize_manifest(right)


def _reject_regression(current, manifest):
    if current is None:
        return None
    if manifest.completed_at < current.completed_at:
        raise BackupError("refusing to publish an older backup")
    if manifest.completed_at == current.completed_at:
        if _same_manifest(current, manifest):
            return current
        raise BackupError("refusing to replace the verified backup")
    return None


def _write_replacement(selected, target, serialized):
    temporary = None
    try:
        descriptor, raw_name = tempfile.mkstemp(
            prefix=".latest-",
            suffix=".tmp",
            dir=selected,
        )
        os.close(descriptor)
        temporary = Path(raw_name)
        if temporary.is_symlink() or temporary.parent.resolve() != selected:
            raise BackupError("refusing to publish outside a backup directory")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        if target.is_symlink():
            raise BackupError("refusing to publish through a symlink")
        os.replace(temporary, target)
        temporary = None
    except BackupError:
        raise
    except OSError:
        raise BackupError("backup publication failed") from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def publish_verified_latest(
    directory,
    payload,
    dump_path,
    *,
    expected_revisions,
    now,
):
    """Replace ``latest.json`` only when the dump and manifest agree.

    Validation runs before the destination is opened. A mismatch, an
    unverified manifest, an older completion time, a different backup
    with the same completion time, a symlink, or an interrupted write
    leaves the previous file in place.
    """

    selected = require_backup_directory(directory)
    manifest = validate_manifest(
        payload,
        expected_revisions=expected_revisions,
        now=now,
    )
    if not manifest.verified:
        raise BackupError("refusing to publish an unverified backup")
    require_dump_checksum(
        dump_path,
        size=manifest.size_bytes,
        digest=manifest.sha256,
    )
    lock = acquire_publication_lock(selected)
    try:
        selected = require_backup_directory(selected)
        require_dump_checksum(
            dump_path,
            size=manifest.size_bytes,
            digest=manifest.sha256,
        )
        target = selected / _LATEST_NAME
        current = _read_verified_pointer(
            target,
            expected_revisions=expected_revisions,
            now=now,
        )
        unchanged = _reject_regression(current, manifest)
        if unchanged is not None:
            return unchanged
        _write_replacement(selected, target, serialize_manifest(manifest))
        return manifest
    finally:
        release_publication_lock(lock)
