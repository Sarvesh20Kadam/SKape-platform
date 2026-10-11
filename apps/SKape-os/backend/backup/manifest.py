"""Validate and serialize a logical backup manifest.

The manifest records one dump. It does not connect to PostgreSQL and
it does not upload the dump.
"""

import json
import re
from datetime import datetime, timezone

from app.schema_revision import schema_revisions_match

from backup.errors import BackupError


REQUIRED_POSTGRES_MAJOR = 16
VERIFIED = "verified"
PENDING = "pending"
_STATUSES = {VERIFIED, PENDING}
_BACKUP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,80}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMPLETED_AT = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)
_FIELDS = (
    "backup_id",
    "completed_at",
    "postgres_major",
    "size_bytes",
    "sha256",
    "schema_revisions",
    "verification_status",
)


class BackupManifest:
    """A manifest that passed validation."""

    def __init__(
        self,
        backup_id,
        completed_at,
        postgres_major,
        size_bytes,
        sha256,
        schema_revisions,
        verification_status,
    ):
        self.backup_id = backup_id
        self.completed_at = completed_at
        self.postgres_major = postgres_major
        self.size_bytes = size_bytes
        self.sha256 = sha256
        self.schema_revisions = schema_revisions
        self.verification_status = verification_status

    @property
    def verified(self):
        return self.verification_status == VERIFIED


def _invalid():
    raise BackupError("backup manifest is invalid")


def _completed_at(value):
    if not isinstance(value, str) or not _COMPLETED_AT.fullmatch(value):
        _invalid()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _invalid()
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(
        parsed
    ):
        _invalid()
    return parsed.astimezone(timezone.utc)


def _require_now(now):
    if (
        not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        raise BackupError("backup completion time is invalid")
    return now.astimezone(timezone.utc)


def _whole_number(value):
    if isinstance(value, bool) or not isinstance(value, int):
        _invalid()
    return value


def validate_manifest(payload, *, expected_revisions, now):
    """Return a manifest whose schema revisions match the expected heads.

    ``expected_revisions`` is the repository head set. A mismatch raises
    ``BackupError`` and does not echo the revision ids. ``now`` is an
    aware clock reading. A completion time after ``now`` is rejected.
    """

    if not isinstance(payload, dict) or set(payload) != set(_FIELDS):
        _invalid()
    backup_id = payload["backup_id"]
    if not isinstance(backup_id, str) or not _BACKUP_ID.fullmatch(backup_id):
        _invalid()
    completed_at = _completed_at(payload["completed_at"])
    if completed_at > _require_now(now):
        raise BackupError("backup completion time is invalid")
    postgres_major = _whole_number(payload["postgres_major"])
    if postgres_major != REQUIRED_POSTGRES_MAJOR:
        raise BackupError("PostgreSQL major version is not 16")
    size_bytes = _whole_number(payload["size_bytes"])
    if size_bytes < 1:
        _invalid()
    digest = payload["sha256"]
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        _invalid()
    revisions = payload["schema_revisions"]
    if (
        not isinstance(revisions, list)
        or not revisions
        or not all(isinstance(item, str) and item.strip() for item in revisions)
    ):
        _invalid()
    if not schema_revisions_match(revisions, expected_revisions):
        raise BackupError("schema revision does not match")
    status = payload["verification_status"]
    if status not in _STATUSES:
        _invalid()
    return BackupManifest(
        backup_id,
        completed_at,
        postgres_major,
        size_bytes,
        digest,
        tuple(sorted(set(revisions))),
        status,
    )


def serialize_manifest(manifest):
    """Serialize a validated manifest as one JSON object."""

    if not isinstance(manifest, BackupManifest):
        _invalid()
    payload = {
        "backup_id": manifest.backup_id,
        "completed_at": manifest.completed_at.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "postgres_major": manifest.postgres_major,
        "size_bytes": manifest.size_bytes,
        "sha256": manifest.sha256,
        "schema_revisions": list(manifest.schema_revisions),
        "verification_status": manifest.verification_status,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def parse_manifest(text, *, expected_revisions, now):
    """Parse manifest JSON and validate it."""

    if not isinstance(text, str) or not text.strip():
        _invalid()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        _invalid()
    return validate_manifest(
        payload,
        expected_revisions=expected_revisions,
        now=now,
    )
