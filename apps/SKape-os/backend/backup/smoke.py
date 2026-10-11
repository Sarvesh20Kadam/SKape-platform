"""Opt-in smoke test for the injected R2 client.

The harness writes two new daily keys and heads ``logical/latest.json``
before and after. It does not publish that pointer, delete an object,
create a bucket, or open a database. Cleanup belongs to a separate
operator. The smoke token must not have permission to delete objects.

Nothing is contacted unless ``SKAPE_R2_SMOKE`` is ``1`` and the bucket
name identifies a non-production bucket. Credentials are not printed.
"""

import os
import secrets
import sys
from datetime import datetime, timezone

from backup.errors import BackupError
from backup.r2 import LATEST_KEY, StorePreconditionError
from backup.r2_client import (
    _ACCESS_KEY_ID,
    _BUCKET,
    _ENDPOINT_URL,
    _REGION,
    _SECRET_ACCESS_KEY,
    R2Client,
    create_r2_client,
)
from backup.retention import object_key_for


_NOT_ENABLED = "backup smoke is not enabled"
_INVALID = "backup smoke configuration is invalid"
_FAILED = "backup smoke failed"
_EXISTS = "backup smoke object already exists"
_DUPLICATE_SUCCEEDED = "backup smoke duplicate create succeeded"
_STALE_ACCEPTED = "backup smoke stale etag was accepted"
_MISMATCH = "backup smoke download did not match"
_POINTER_CHANGED = "backup smoke pointer changed"
_CLIENT_INVALID = "backup object store configuration is invalid"
_STORE_FAILED = "backup object store failed"
_KEY_INVALID = "backup object key is invalid"
_SAFE_MESSAGES = {
    _NOT_ENABLED,
    _INVALID,
    _FAILED,
    _EXISTS,
    _DUPLICATE_SUCCEEDED,
    _STALE_ACCEPTED,
    _MISMATCH,
    _POINTER_CHANGED,
    _CLIENT_INVALID,
    _STORE_FAILED,
    _KEY_INVALID,
}
_FORBIDDEN_SEGMENTS = {"prod", "production"}
_FIRST_DUMP = b"skape-r2-smoke-dump-v1"
_SECOND_DUMP = b"skape-r2-smoke-dump-v2"
_FIRST_JSON = b'{"smoke":"v1"}'
_SECOND_JSON = b'{"smoke":"v2"}'


class SmokeConfig:
    """Explicit smoke settings. ``repr`` omits the secret."""

    def __init__(
        self,
        *,
        endpoint_url,
        region_name,
        bucket,
        access_key_id,
        secret_access_key,
    ):
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        self.bucket = bucket
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key

    def __repr__(self):
        return "SmokeConfig()"


def _enabled(environ):
    return environ.get("SKAPE_R2_SMOKE") == "1"


def _text(environ, name, pattern):
    value = environ.get(name)
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise BackupError(_INVALID)
    return value


def _bucket_name(value):
    if not isinstance(value, str) or _BUCKET.fullmatch(value) is None:
        raise BackupError(_INVALID)
    if not value.startswith("smoke-"):
        raise BackupError(_INVALID)
    if _FORBIDDEN_SEGMENTS.intersection(value.split("-")):
        raise BackupError(_INVALID)
    return value


def load_smoke_config(environ):
    """Read explicit smoke settings. This does not construct a client."""

    if not _enabled(environ):
        raise BackupError(_NOT_ENABLED)
    endpoint_url = _text(environ, "SKAPE_R2_ENDPOINT", _ENDPOINT_URL)
    region_name = _text(environ, "SKAPE_R2_REGION", _REGION)
    bucket = _bucket_name(environ.get("SKAPE_R2_BUCKET"))
    access_key_id = _text(environ, "SKAPE_R2_ACCESS_KEY_ID", _ACCESS_KEY_ID)
    secret_access_key = _text(
        environ,
        "SKAPE_R2_SECRET_ACCESS_KEY",
        _SECRET_ACCESS_KEY,
    )
    return SmokeConfig(
        endpoint_url=endpoint_url,
        region_name=region_name,
        bucket=bucket,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
    )


def new_smoke_id(now, nonce):
    """Return one daily backup id that this harness may write."""

    if now.tzinfo is None or now.utcoffset() != timezone.utc.utcoffset(now):
        raise BackupError(_FAILED)
    if not isinstance(nonce, str) or len(nonce) != 6:
        raise BackupError(_FAILED)
    if any(character not in "0123456789abcdef" for character in nonce):
        raise BackupError(_FAILED)
    return "smoke-%s-%s" % (now.strftime("%Y%m%dT%H%M%SZ"), nonce)


def _pointer(info):
    if info is None:
        return None
    size = getattr(info, "size", None)
    etag = getattr(info, "etag", None)
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise BackupError(_FAILED)
    if not isinstance(etag, str) or not etag:
        raise BackupError(_FAILED)
    return (size, etag)


def _keys(backup_id):
    dump_key = object_key_for("daily", backup_id)
    if not dump_key.endswith(".dump"):
        raise BackupError(_FAILED)
    return dump_key, dump_key[: -len(".dump")] + ".json"


def _exercise(store, key, first, second):
    if store.head(key) is not None:
        raise BackupError(_EXISTS)
    created = store.put(key, first, if_none_match="*")
    try:
        store.put(key, first, if_none_match="*")
    except StorePreconditionError:
        conflicted = True
    else:
        conflicted = False
    if not conflicted:
        raise BackupError(_DUPLICATE_SUCCEEDED)
    body, fetched = store.get(key)
    if body != first or fetched.etag != created.etag:
        raise BackupError(_MISMATCH)
    current = store.head(key)
    if current is None:
        raise BackupError(_FAILED)
    store.put(key, second, if_match=current.etag)
    try:
        store.put(key, first, if_match=current.etag)
    except StorePreconditionError:
        rejected = True
    else:
        rejected = False
    if not rejected:
        raise BackupError(_STALE_ACCEPTED)
    body, fetched = store.get(key)
    final = store.head(key)
    if (
        final is None
        or body != second
        or fetched.etag != final.etag
        or fetched.size != len(second)
        or final.size != len(second)
    ):
        raise BackupError(_MISMATCH)


def run_smoke(store, *, backup_id):
    """Exercise conditional writes on two new daily keys.

    ``logical/latest.json`` is read before and after. It is not written.
    """

    try:
        dump_key, json_key = _keys(backup_id)
        before = _pointer(store.head(LATEST_KEY))
        _exercise(store, dump_key, _FIRST_DUMP, _SECOND_DUMP)
        _exercise(store, json_key, _FIRST_JSON, _SECOND_JSON)
        if _pointer(store.head(LATEST_KEY)) != before:
            raise BackupError(_POINTER_CHANGED)
    except BackupError:
        raise
    except Exception:
        raise BackupError(_FAILED) from None
    return dump_key, json_key


def _write(stream, message):
    stream.write(message)
    if not message.endswith("\n"):
        stream.write("\n")


def main(
    environ=None,
    *,
    client_factory=None,
    store_factory=None,
    id_factory=None,
    stdout=None,
    stderr=None,
):
    """Run the smoke test when explicit opt-in configuration is present."""

    selected = os.environ if environ is None else environ
    output = sys.stdout if stdout is None else stdout
    error = sys.stderr if stderr is None else stderr
    try:
        config = load_smoke_config(selected)
    except BackupError as exc:
        _write(error, _safe_message(exc, _INVALID))
        return 1
    factory = create_r2_client if client_factory is None else client_factory
    build_store = R2Client if store_factory is None else store_factory
    if id_factory is None:
        def id_factory():
            return new_smoke_id(
                datetime.now(timezone.utc),
                secrets.token_hex(3),
            )
    try:
        client = factory(
            endpoint_url=config.endpoint_url,
            region_name=config.region_name,
            access_key_id=config.access_key_id,
            secret_access_key=config.secret_access_key,
        )
        store = build_store(client, config.bucket)
        backup_id = id_factory()
        dump_key, json_key = _keys(backup_id)
    except BackupError as exc:
        _write(error, _safe_message(exc, _INVALID))
        return 1
    except Exception:
        _write(error, _INVALID)
        return 1
    try:
        run_smoke(store, backup_id=backup_id)
    except BackupError as exc:
        _write_failure(error, exc, dump_key, json_key)
        return 1
    except Exception:
        _write_failure(error, BackupError(_FAILED), dump_key, json_key)
        return 1
    _write(output, "backup smoke completed")
    _write(output, dump_key)
    _write(output, json_key)
    return 0


def _safe_message(exc, fallback):
    message = str(exc)
    if message in _SAFE_MESSAGES:
        return message
    return fallback


def _write_failure(error, exc, dump_key, json_key):
    _write(error, _safe_message(exc, _FAILED))
    _write(error, dump_key)
    _write(error, json_key)


if __name__ == "__main__":
    raise SystemExit(main())
