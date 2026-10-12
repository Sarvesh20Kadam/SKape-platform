"""Decide which verified copies may be deleted.

Each retained copy resolves to its own class-specific object key,
``logical/<class>/<backup-id>.dump``. Two records that name the same
physical object are rejected, so they cannot be counted as independent
copies. A daily object that is still referenced by a weekly or monthly
copy is never a deletion candidate.

The result never includes the newest verified copy. It also never
includes a copy when deleting it would leave fewer than the required
number of verified copies in that class. Unverified copies are ignored
and are not deletion candidates. This module does not delete files.
"""

import re

from backup.errors import BackupError
from backup.manifest import BackupManifest


MINIMUM_VERIFIED_COPIES = {
    "daily": 14,
    "weekly": 8,
    "monthly": 6,
}
_CLASSES = tuple(MINIMUM_VERIFIED_COPIES)
_BACKUP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,80}$")
_OBJECT_KEY = re.compile(
    r"^logical/(daily|weekly|monthly)/[A-Za-z0-9][A-Za-z0-9_-]{0,80}\.dump$"
)


def object_key_for(backup_class, backup_id):
    """Return the object key for one class-specific copy."""

    if backup_class not in MINIMUM_VERIFIED_COPIES:
        raise BackupError("backup class is invalid")
    if not isinstance(backup_id, str) or not _BACKUP_ID.fullmatch(backup_id):
        raise BackupError("backup object key is invalid")
    return f"logical/{backup_class}/{backup_id}.dump"


class ClassifiedBackup:
    """One manifest stored as one class-specific object."""

    def __init__(
        self,
        manifest,
        backup_class,
        *,
        object_key=None,
        physical_object_key=None,
        source_backup_id=None,
    ):
        if not isinstance(manifest, BackupManifest):
            raise BackupError("backup manifest is missing")
        if backup_class not in MINIMUM_VERIFIED_COPIES:
            raise BackupError("backup class is invalid")
        canonical = object_key_for(backup_class, manifest.backup_id)
        if object_key is None:
            object_key = canonical
        if object_key != canonical:
            raise BackupError("backup object key conflicts")
        if physical_object_key is None:
            physical_object_key = canonical
        elif (
            not isinstance(physical_object_key, str)
            or _OBJECT_KEY.fullmatch(physical_object_key) is None
        ):
            raise BackupError("backup object key is invalid")
        if source_backup_id is not None:
            if backup_class == "daily" or not isinstance(source_backup_id, str):
                raise BackupError("backup reference is ambiguous")
            if _BACKUP_ID.fullmatch(source_backup_id) is None:
                raise BackupError("backup reference is ambiguous")
        self.manifest = manifest
        self.backup_class = backup_class
        self.object_key = object_key
        self.physical_object_key = physical_object_key
        self.source_backup_id = source_backup_id


def _protected_daily_keys(entries):
    daily_ids = {
        entry.manifest.backup_id
        for entry in entries
        if entry.backup_class == "daily"
    }
    protected = set()
    for entry in entries:
        if entry.backup_class == "daily":
            continue
        if entry.manifest.backup_id in daily_ids:
            protected.add(object_key_for("daily", entry.manifest.backup_id))
        if entry.source_backup_id is None:
            continue
        if entry.source_backup_id not in daily_ids:
            raise BackupError("backup reference is ambiguous")
        protected.add(object_key_for("daily", entry.source_backup_id))
    return protected


def copies_authorized_for_deletion(entries):
    """Return verified copies whose deletion stays inside the policy.

    Copies that share the newest verified completion time are kept, even
    when that means a class stays above its minimum. A daily copy whose
    object key is still referenced by a weekly or monthly record is kept
    as well.
    """

    if not isinstance(entries, (list, tuple)):
        raise BackupError("backup retention input is invalid")
    verified = []
    seen_ids = set()
    seen_physical = set()
    for entry in entries:
        if not isinstance(entry, ClassifiedBackup):
            raise BackupError("backup retention input is invalid")
        if entry.backup_class not in _CLASSES:
            raise BackupError("backup class is invalid")
        if not isinstance(entry.manifest, BackupManifest):
            raise BackupError("backup manifest is missing")
        expected = object_key_for(entry.backup_class, entry.manifest.backup_id)
        if entry.object_key != expected:
            raise BackupError("backup object key conflicts")
        identity = (entry.backup_class, entry.manifest.backup_id)
        if identity in seen_ids:
            raise BackupError("duplicate retained backup")
        seen_ids.add(identity)
        if entry.physical_object_key in seen_physical:
            raise BackupError("backup object key conflicts")
        seen_physical.add(entry.physical_object_key)
        if entry.physical_object_key != entry.object_key:
            raise BackupError("backup object key conflicts")
        if entry.manifest.verified:
            verified.append(entry)
    protected = _protected_daily_keys(entries)
    if not verified:
        return []
    newest = max(entry.manifest.completed_at for entry in verified)
    authorized = []
    for backup_class in _CLASSES:
        group = sorted(
            (
                entry
                for entry in verified
                if entry.backup_class == backup_class
            ),
            key=lambda entry: (
                entry.manifest.completed_at,
                entry.manifest.backup_id,
            ),
        )
        minimum = MINIMUM_VERIFIED_COPIES[backup_class]
        if len(group) <= minimum:
            continue
        for entry in group[: len(group) - minimum]:
            if entry.manifest.completed_at == newest:
                continue
            if entry.object_key in protected:
                continue
            authorized.append(entry)
    return authorized
