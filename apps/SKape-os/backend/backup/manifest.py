"""Validate and serialize a logical backup manifest.

The manifest records one dump. It does not connect to PostgreSQL and
it does not upload the dump.
"""

import json
import re
import weakref
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


_FROM_VALIDATION = object()
_SEALED = weakref.WeakKeyDictionary()


def _sealed_values(manifest):
    try:
        return _SEALED[manifest]
    except KeyError:
        _invalid()


def _field(index):
    """Read one sealed field and reject later assignment."""

    def getter(manifest):
        return _sealed_values(manifest)[index]

    def setter(manifest, value):
        _invalid()

    def deleter(manifest):
        _invalid()

    return property(getter, setter, deleter)


class BackupManifest:
    """A manifest that passed :func:`validate_manifest`.

    Direct construction is rejected. After validation the fields are
    fixed: assignment, deletion, and instance-attribute replacement do
    not change the values retention and publication read.
    """

    __slots__ = ("__weakref__",)

    def __init__(
        self,
        backup_id,
        completed_at,
        postgres_major,
        size_bytes,
        sha256,
        schema_revisions,
        verification_status,
        validation_token=None,
    ):
        if validation_token is not _FROM_VALIDATION:
            _invalid()
        if not isinstance(backup_id, str) or not _BACKUP_ID.fullmatch(backup_id):
            _invalid()
        if (
            not isinstance(completed_at, datetime)
            or completed_at.tzinfo is None
            or completed_at.utcoffset() is None
            or completed_at.utcoffset() != timezone.utc.utcoffset(completed_at)
        ):
            _invalid()
        if (
            isinstance(postgres_major, bool)
            or postgres_major != REQUIRED_POSTGRES_MAJOR
        ):
            _invalid()
        if (
            isinstance(size_bytes, bool)
            or not isinstance(size_bytes, int)
            or size_bytes < 1
        ):
            _invalid()
        if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
            _invalid()
        if (
            not isinstance(schema_revisions, tuple)
            or not schema_revisions
            or not all(
                isinstance(item, str) and item.strip()
                for item in schema_revisions
            )
        ):
            _invalid()
        if verification_status not in _STATUSES:
            _invalid()
        _SEALED[self] = (
            backup_id,
            completed_at,
            postgres_major,
            size_bytes,
            sha256,
            schema_revisions,
            verification_status,
        )

    def __setattr__(self, name, value):
        _invalid()

    def __delattr__(self, name):
        _invalid()

    backup_id = _field(0)
    completed_at = _field(1)
    postgres_major = _field(2)
    size_bytes = _field(3)
    sha256 = _field(4)
    schema_revisions = _field(5)
    verification_status = _field(6)

    @property
    def verified(self):
        return self.verification_status == VERIFIED

    @verified.setter
    def verified(self, value):
        _invalid()

    @verified.deleter
    def verified(self):
        _invalid()


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
        _FROM_VALIDATION,
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
