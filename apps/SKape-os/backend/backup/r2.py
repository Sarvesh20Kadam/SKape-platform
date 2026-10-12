"""Publish one verified logical backup through an injected object store.

The adapter does not create a client, choose an endpoint, or open a
network connection. The caller supplies an object store with ``head``,
``get``, and ``put``. There is no delete operation.

``head(key)`` returns :class:`ObjectInfo` or ``None`` when the key is
absent. ``get(key)`` returns ``(body, ObjectInfo)``. ``put`` writes the
body only when its precondition holds:

- ``if_none_match="*"`` creates the key when it is absent.
- ``if_match`` replaces the key only when the current ETag is that
  token.

A lost precondition raises :class:`StorePreconditionError` and leaves
the stored object unchanged, except when a concurrent writer won the
race. The ETag is only a concurrency token. It is not a SHA-256 digest.

Object keys are ``logical/<class>/<backup-id>.dump``,
``logical/<class>/<backup-id>.json``, and ``logical/latest.json``.
The class and any source backup id stay out of the manifest body.
``latest`` is written only after the stored dump and manifest match.
``backup.r2_client`` adapts an injected S3 client to this protocol.
"""

import hashlib
from pathlib import Path

from backup.dump import require_dump_checksum
from backup.errors import BackupError
from backup.manifest import parse_manifest, serialize_manifest, validate_manifest
from backup.retention import object_key_for


LATEST_KEY = "logical/latest.json"


class ObjectInfo:
    """Size and concurrency token for one stored object."""

    def __init__(self, size, etag):
        self.size = size
        self.etag = etag


class StorePreconditionError(BackupError):
    """A conditional write did not match the object observed earlier."""


def _publication_failed():
    raise BackupError("backup publication failed")


def _checksum_failed():
    raise BackupError("backup checksum does not match")


def _manifest_conflicts():
    raise BackupError("backup manifest conflicts")


def _invoke(func, *args, **kwargs):
    """Call the store and replace its exception with a fixed message."""

    try:
        return func(*args, **kwargs)
    except StorePreconditionError:
        failed = "precondition"
    except Exception:
        failed = "error"
    if failed == "precondition":
        raise StorePreconditionError(
            "backup publication precondition failed"
        )
    _publication_failed()


def _object_info(value):
    if not isinstance(value, ObjectInfo):
        _publication_failed()
    if isinstance(value.size, bool) or not isinstance(value.size, int):
        _publication_failed()
    if value.size < 0:
        _publication_failed()
    etag = value.etag
    if not isinstance(etag, str) or not etag or len(etag) > 256:
        _publication_failed()
    if any(character in etag for character in "\r\n\x00"):
        _publication_failed()
    return value


def _head(store, key):
    info = _invoke(store.head, key)
    if info is None:
        return None
    return _object_info(info)


def _get(store, key):
    fetched = _invoke(store.get, key)
    if not isinstance(fetched, tuple) or len(fetched) != 2:
        _publication_failed()
    body, info = fetched
    if not isinstance(body, (bytes, bytearray)):
        _publication_failed()
    return bytes(body), _object_info(info)


def _put(store, key, body, *, if_match=None, if_none_match=None):
    if (if_match is None) == (if_none_match is None):
        _publication_failed()
    info = _invoke(
        store.put,
        key,
        body,
        if_match=if_match,
        if_none_match=if_none_match,
    )
    return _object_info(info)


def _digest(body):
    return hashlib.sha256(body).hexdigest()


def _read_local_dump(path, manifest):
    require_dump_checksum(
        path,
        size=manifest.size_bytes,
        digest=manifest.sha256,
    )
    try:
        body = Path(path).read_bytes()
    except OSError:
        body = None
    if body is None:
        _checksum_failed()
    if len(body) != manifest.size_bytes or _digest(body) != manifest.sha256:
        _checksum_failed()
    return body


def _manifest_key(dump_key):
    if not dump_key.endswith(".dump"):
        _publication_failed()
    return dump_key[: -len(".dump")] + ".json"


def _same_observation(head_info, body, fetched):
    return (
        head_info is not None
        and head_info.size == fetched.size
        and head_info.etag == fetched.etag
        and len(body) == fetched.size
    )


def _read_stable(store, key):
    """Return the body and info when head and get describe one object."""

    info = _head(store, key)
    if info is None:
        return None
    body, fetched = _get(store, key)
    if not _same_observation(info, body, fetched):
        _publication_failed()
    return body, fetched


def _dump_matches(body, manifest):
    return (
        body.startswith(b"PGDMP")
        and len(body) == manifest.size_bytes
        and _digest(body) == manifest.sha256
    )


def _store_dump(store, key, body, manifest):
    if _head(store, key) is None:
        try:
            _put(store, key, body, if_none_match="*")
        except StorePreconditionError:
            pass
    observed = _read_stable(store, key)
    if observed is None or not _dump_matches(observed[0], manifest):
        _checksum_failed()


def _store_sidecar(store, key, canonical):
    if _head(store, key) is None:
        try:
            _put(store, key, canonical, if_none_match="*")
        except StorePreconditionError:
            pass
    observed = _read_stable(store, key)
    if observed is None or observed[0] != canonical:
        _manifest_conflicts()


def _pointer_manifest(body, *, expected_revisions, now):
    try:
        text = body.decode("utf-8")
    except UnicodeError:
        raise BackupError(
            "refusing to replace an unverified backup pointer"
        ) from None
    try:
        current = parse_manifest(
            text,
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


def _read_pointer(store, *, expected_revisions, now):
    observed = _read_stable(store, LATEST_KEY)
    if observed is None:
        return None, None
    body, info = observed
    current = _pointer_manifest(
        body,
        expected_revisions=expected_revisions,
        now=now,
    )
    return current, info.etag


def _require_newer_or_same(current, manifest):
    """Return True when ``latest`` already names this manifest."""

    if current is None:
        return False
    if manifest.completed_at < current.completed_at:
        raise BackupError("refusing to publish an older backup")
    if manifest.completed_at == current.completed_at:
        if serialize_manifest(current) == serialize_manifest(manifest):
            return True
        raise BackupError("refusing to replace the verified backup")
    return False


def _accept_winner_or_fail(store, canonical, *, expected_revisions, now):
    """Re-read ``latest`` once after a lost conditional write."""

    observed = _read_stable(store, LATEST_KEY)
    if observed is None:
        raise BackupError("refusing to replace the verified backup")
    body, _info = observed
    try:
        current = _pointer_manifest(
            body,
            expected_revisions=expected_revisions,
            now=now,
        )
    except BackupError:
        raise
    if serialize_manifest(current).encode("utf-8") == canonical:
        return
    raise BackupError("refusing to replace the verified backup")


def _publish_pointer(store, canonical, manifest, *, expected_revisions, now):
    current, etag = _read_pointer(
        store,
        expected_revisions=expected_revisions,
        now=now,
    )
    if _require_newer_or_same(current, manifest):
        return
    lost = False
    try:
        if etag is None:
            _put(store, LATEST_KEY, canonical, if_none_match="*")
        else:
            _put(store, LATEST_KEY, canonical, if_match=etag)
    except StorePreconditionError:
        lost = True
    if lost:
        _accept_winner_or_fail(
            store,
            canonical,
            expected_revisions=expected_revisions,
            now=now,
        )


def publish_remote_backup(
    store,
    *,
    backup_class,
    dump_path,
    payload,
    expected_revisions,
    now,
):
    """Upload one verified dump and publish ``logical/latest.json`` last.

    A pending manifest, a local checksum mismatch, or a remote object
    that differs is rejected. A lost pointer race is re-read once. The
    winner is kept when it is this same canonical manifest. Otherwise
    the attempt fails and does not write ``latest`` again.
    """

    manifest = validate_manifest(
        payload,
        expected_revisions=expected_revisions,
        now=now,
    )
    if not manifest.verified:
        raise BackupError("refusing to publish an unverified backup")
    body = _read_local_dump(dump_path, manifest)
    dump_key = object_key_for(backup_class, manifest.backup_id)
    _store_dump(store, dump_key, body, manifest)
    canonical = serialize_manifest(manifest).encode("utf-8")
    _store_sidecar(store, _manifest_key(dump_key), canonical)
    _publish_pointer(
        store,
        canonical,
        manifest,
        expected_revisions=expected_revisions,
        now=now,
    )
    return manifest
