"""Decide whether the latest verified backup is older than 24 hours.

Malformed metadata and an unverified manifest fail closed. A backup
whose completion time is in the future is invalid. A backup completed
exactly 24 hours ago is still fresh.
"""

from datetime import datetime, timedelta, timezone

from backup.errors import BackupError
from backup.manifest import validate_manifest


STALE_AFTER = timedelta(hours=24)


class StaleCheck:
    """Result of a valid verified manifest."""

    def __init__(self, status, completed_at):
        self.status = status
        self.completed_at = completed_at

    @property
    def stale(self):
        return self.status == "stale"


def check_stale(payload, *, expected_revisions, now):
    """Validate latest-backup metadata and report whether it is stale."""

    if not isinstance(now, datetime) or now.tzinfo is None:
        raise BackupError("backup completion time is invalid")
    now = now.astimezone(timezone.utc)
    manifest = validate_manifest(
        payload,
        expected_revisions=expected_revisions,
        now=now,
    )
    if not manifest.verified:
        raise BackupError("backup is not verified")
    age = now - manifest.completed_at
    if age < timedelta(0):
        raise BackupError("backup completion time is invalid")
    status = "stale" if age > STALE_AFTER else "fresh"
    return StaleCheck(status, manifest.completed_at)
