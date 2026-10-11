"""Validate a custom-format PostgreSQL dump file.

The checks match the logical recovery drill: the file is non-empty,
it starts with the custom-format marker, and its SHA-256 is calculated
from the file bytes. This module does not run ``pg_dump``.
"""

import hashlib
from pathlib import Path

from backup.errors import BackupError


CUSTOM_FORMAT_MAGIC = b"PGDMP"
_HASH_CHUNK_BYTES = 1024 * 1024


class DumpFile:
    """Size and digest of one accepted dump file."""

    def __init__(self, size, sha256):
        self.size = size
        self.sha256 = sha256


def sha256_file(path):
    """Hash a file in chunks. The path is not logged."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_dump_file(path):
    """Accept one regular custom-format dump file."""

    selected = Path(path)
    if selected.is_symlink() or not selected.is_file():
        raise BackupError("pg_dump did not write a custom-format backup")
    size = selected.stat().st_size
    if size <= 0:
        raise BackupError("pg_dump produced an empty backup")
    with selected.open("rb") as handle:
        magic = handle.read(len(CUSTOM_FORMAT_MAGIC))
    if magic != CUSTOM_FORMAT_MAGIC:
        raise BackupError("pg_dump did not write a custom-format backup")
    return DumpFile(size, sha256_file(selected))


def require_dump_checksum(path, *, size, digest):
    """Reject a dump whose size or SHA-256 differs from the manifest."""

    info = validate_dump_file(path)
    if info.size != size or info.sha256 != digest:
        raise BackupError("backup checksum does not match")
    return info
