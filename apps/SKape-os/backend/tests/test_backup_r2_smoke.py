"""Offline checks for the opt-in R2 smoke harness.

The store is fake. These tests do not import boto3, contact Cloudflare,
or open a network connection.
"""

import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backup.errors import BackupError
from backup.r2 import LATEST_KEY, ObjectInfo, StorePreconditionError
from backup.smoke import (
    SmokeConfig,
    load_smoke_config,
    main,
    new_smoke_id,
    run_smoke,
)


ACCOUNT = "a" * 32
ENDPOINT = "https://%s.r2.cloudflarestorage.com" % ACCOUNT
BUCKET = "smoke-nonprod"
ACCESS = "b" * 32
SECRET = "c" * 64
NOW = datetime(2026, 10, 11, 18, 15, tzinfo=timezone.utc)
BACKUP_ID = "smoke-20261011T181500Z-abc123"


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _etag(body):
    return '"%s"' % hashlib.md5(body).hexdigest()


def _environ(**overrides):
    values = {
        "SKAPE_R2_SMOKE": "1",
        "SKAPE_R2_ENDPOINT": ENDPOINT,
        "SKAPE_R2_REGION": "auto",
        "SKAPE_R2_BUCKET": BUCKET,
        "SKAPE_R2_ACCESS_KEY_ID": ACCESS,
        "SKAPE_R2_SECRET_ACCESS_KEY": SECRET,
        "AWS_ACCESS_KEY_ID": "e" * 32,
        "AWS_SECRET_ACCESS_KEY": "f" * 64,
        "AWS_PROFILE": "default",
    }
    values.update(overrides)
    return values


class FakeStore:
    """Conditional head/get/put store. It has no delete."""

    def __init__(self, *, latest=None):
        self.objects = {}
        self.latest = latest
        self.calls = []

    def head(self, key):
        self.calls.append(("head", key))
        if key == LATEST_KEY:
            return self.latest
        item = self.objects.get(key)
        if item is None:
            return None
        body, etag = item
        return ObjectInfo(len(body), etag)

    def get(self, key):
        self.calls.append(("get", key))
        body, etag = self.objects[key]
        return body, ObjectInfo(len(body), etag)

    def put(self, key, body, *, if_match=None, if_none_match=None):
        self.calls.append(("put", key, if_match, if_none_match))
        if key == LATEST_KEY:
            raise AssertionError("latest write")
        current = self.objects.get(key)
        if if_none_match == "*" and if_match is None:
            if current is not None:
                raise StorePreconditionError(
                    "backup publication precondition failed"
                )
            etag = _etag(body)
            self.objects[key] = (bytes(body), etag)
            return ObjectInfo(len(body), etag)
        if if_match is not None and if_none_match is None:
            if current is None or current[1] != if_match:
                raise StorePreconditionError(
                    "backup publication precondition failed"
                )
            etag = _etag(body)
            self.objects[key] = (bytes(body), etag)
            return ObjectInfo(len(body), etag)
        raise BackupError("backup smoke failed")


def test_opt_in_stops_before_client_construction():
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        raise AssertionError("client")

    stderr = io.StringIO()
    code = main(
        {"SKAPE_R2_SECRET_ACCESS_KEY": SECRET},
        client_factory=factory,
        stderr=stderr,
        stdout=io.StringIO(),
    )
    _require(code == 1, "exit mismatch")
    _require(calls == [], "client constructed")
    text = stderr.getvalue()
    _require(text == "backup smoke is not enabled\n", "message mismatch")
    _require(SECRET not in text, "secret leaked")


def test_invalid_configuration_is_hidden_and_does_not_construct():
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)

    samples = [
        {"SKAPE_R2_BUCKET": "production-backups"},
        {"SKAPE_R2_BUCKET": "smoke-prod"},
        {"SKAPE_R2_BUCKET": "smoke-production"},
        {"SKAPE_R2_BUCKET": "Smoke-Nonprod"},
        {"SKAPE_R2_REGION": "us-east-1"},
        {"SKAPE_R2_ENDPOINT": "https://user:%s@example.invalid" % SECRET},
        {"SKAPE_R2_ENDPOINT": "http://%s.r2.cloudflarestorage.com" % ACCOUNT},
        {"SKAPE_R2_ACCESS_KEY_ID": "short"},
        {"SKAPE_R2_SECRET_ACCESS_KEY": "LEAKED-" + SECRET},
        {"SKAPE_R2_SMOKE": "yes"},
    ]
    for override in samples:
        calls.clear()
        stderr = io.StringIO()
        code = main(
            _environ(**override),
            client_factory=factory,
            stderr=stderr,
            stdout=io.StringIO(),
        )
        _require(code == 1, "exit mismatch")
        _require(calls == [], "client constructed")
        text = stderr.getvalue()
        _require(SECRET not in text, "secret leaked")
        _require("https://" not in text, "endpoint leaked")
        _require(
            text
            in {
                "backup smoke is not enabled\n",
                "backup smoke configuration is invalid\n",
            },
            "message mismatch",
        )
        _require("logical/daily/" not in text, "keys listed before a run")


def test_config_repr_hides_the_secret():
    config = load_smoke_config(_environ())
    _require(repr(config) == "SmokeConfig()", "repr mismatch")
    _require(SECRET not in repr(config), "secret leaked")
    _require(config.endpoint_url == ENDPOINT, "endpoint mismatch")
    _require(config.region_name == "auto", "region mismatch")
    _require(config.bucket == BUCKET, "bucket mismatch")
    _require(isinstance(config, SmokeConfig), "type mismatch")


def test_smoke_id_is_a_daily_object_id():
    identifier = new_smoke_id(NOW, "abc123")
    _require(identifier == BACKUP_ID, "id mismatch")
    with pytest.raises(BackupError, match="backup smoke failed"):
        new_smoke_id(datetime(2026, 10, 11, 18, 15), "abc123")


def test_harness_exercises_conditional_writes_without_touching_latest():
    store = FakeStore(latest=ObjectInfo(4, '"' + ("ab" * 16) + '"'))
    dump_key, json_key = run_smoke(store, backup_id=BACKUP_ID)
    _require(
        dump_key == "logical/daily/%s.dump" % BACKUP_ID,
        "dump key mismatch",
    )
    _require(
        json_key == "logical/daily/%s.json" % BACKUP_ID,
        "json key mismatch",
    )
    puts = [call for call in store.calls if call[0] == "put"]
    _require(len(puts) == 8, "put count mismatch")
    _require({call[1] for call in puts} == {dump_key, json_key}, "put keys")
    _require(all(call[1] != LATEST_KEY for call in puts), "latest written")
    heads = [call for call in store.calls if call[0] == "head"]
    _require(heads[0] == ("head", LATEST_KEY), "missing preflight")
    _require(heads[-1] == ("head", LATEST_KEY), "missing postcheck")
    _require(not hasattr(store, "delete") or "delete" not in str(store.calls), "delete")
    dump_puts = [call for call in puts if call[1] == dump_key]
    created = _etag(b"skape-r2-smoke-dump-v1")
    _require(dump_puts[0][3] == "*", "create precondition missing")
    _require(dump_puts[0][2] is None, "create also matched")
    _require(dump_puts[1][3] == "*", "duplicate precondition missing")
    _require(dump_puts[2][2] == created, "replacement etag mismatch")
    _require(dump_puts[3][2] == created, "stale etag was not the observed token")
    _require(store.objects[dump_key][0] == b"skape-r2-smoke-dump-v2", "dump bytes mismatch")
    _require(store.objects[json_key][0] == b'{"smoke":"v2"}', "json bytes mismatch")
    _require(
        store.objects[dump_key][1] == _etag(b"skape-r2-smoke-dump-v2"),
        "dump etag mismatch",
    )


def test_pointer_change_fails_closed():
    class Changing(FakeStore):
        def __init__(self):
            super().__init__()
            self.latest_heads = 0

        def head(self, key):
            info = super().head(key)
            if key != LATEST_KEY:
                return info
            self.latest_heads += 1
            if self.latest_heads > 1:
                return ObjectInfo(1, '"' + ("cd" * 16) + '"')
            return info

    with pytest.raises(BackupError, match="backup smoke pointer changed") as caught:
        run_smoke(Changing(), backup_id=BACKUP_ID)
    _require(caught.value.__cause__ is None, "cause set")
    _require(SECRET not in str(caught.value), "secret leaked")


def test_existing_object_is_not_overwritten():
    store = FakeStore()
    key = "logical/daily/%s.dump" % BACKUP_ID
    store.objects[key] = (b"kept", _etag(b"kept"))
    with pytest.raises(BackupError, match="backup smoke object already exists"):
        run_smoke(store, backup_id=BACKUP_ID)
    _require(store.objects[key][0] == b"kept", "existing object changed")
    _require(not any(call[0] == "put" for call in store.calls), "put attempted")


def test_main_uses_explicit_configuration_and_the_wrapper():
    recorded = {}
    store = FakeStore()

    def factory(**kwargs):
        recorded.update(kwargs)
        return object()

    def build_store(client, bucket):
        recorded["client"] = client
        recorded["bucket"] = bucket
        return store

    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(
        _environ(),
        client_factory=factory,
        store_factory=build_store,
        id_factory=lambda: BACKUP_ID,
        stdout=stdout,
        stderr=stderr,
    )
    _require(code == 0, "exit mismatch")
    _require(stderr.getvalue() == "", "stderr mismatch")
    text = stdout.getvalue()
    _require(SECRET not in text, "secret leaked")
    _require(ACCESS not in text, "access key leaked")
    _require(ENDPOINT not in text, "endpoint leaked")
    _require("backup smoke completed\n" in text, "completion missing")
    _require("logical/daily/%s.dump\n" % BACKUP_ID in text, "dump key missing")
    _require("logical/daily/%s.json\n" % BACKUP_ID in text, "json key missing")
    _require(recorded["endpoint_url"] == ENDPOINT, "endpoint mismatch")
    _require(recorded["region_name"] == "auto", "region mismatch")
    _require(recorded["access_key_id"] == ACCESS, "access key mismatch")
    _require(recorded["secret_access_key"] == SECRET, "secret mismatch")
    _require("aws_session_token" not in recorded, "session token forwarded")
    _require(recorded["bucket"] == BUCKET, "bucket mismatch")
    _require(recorded["access_key_id"] != "e" * 32, "ambient access key used")
    source = Path(__file__).resolve().parents[1].joinpath(
        "backup", "smoke.py"
    ).read_text(encoding="utf-8")
    _require("publish_remote_backup" not in source, "publication imported")
    _require("delete_object" not in source, "delete imported")
    _require("os.environ" in source, "environment lookup missing")


DUMP_KEY = "logical/daily/%s.dump" % BACKUP_ID
JSON_KEY = "logical/daily/%s.json" % BACKUP_ID


class StageStore(FakeStore):
    """Fails at one smoke stage and records whether delete was called."""

    def __init__(self, mode):
        super().__init__(latest=ObjectInfo(4, '"' + ("ab" * 16) + '"'))
        self.mode = mode
        self.creates = 0
        self.latest_heads = 0
        self.deleted = False

    def delete(self, *args, **kwargs):
        self.deleted = True
        raise AssertionError("delete")

    def head(self, key):
        if key == LATEST_KEY:
            self.latest_heads += 1
            if self.mode == "final" and self.latest_heads > 1:
                raise RuntimeError(SECRET + " " + ENDPOINT + " " + BUCKET)
        if self.mode == "second-object" and key == JSON_KEY:
            raise RuntimeError(SECRET + " " + ENDPOINT + " " + BUCKET)
        return super().head(key)

    def put(self, key, body, *, if_match=None, if_none_match=None):
        if (
            self.mode == "after-create"
            and if_none_match == "*"
            and self.creates >= 1
        ):
            raise RuntimeError(SECRET + " " + ENDPOINT + " " + BUCKET)
        result = super().put(
            key,
            body,
            if_match=if_match,
            if_none_match=if_none_match,
        )
        if if_none_match == "*":
            self.creates += 1
        return result


def _assert_failure_keys(text):
    _require(SECRET not in text, "secret leaked")
    _require(ACCESS not in text, "access key leaked")
    _require(ENDPOINT not in text, "endpoint leaked")
    _require(BUCKET not in text, "bucket leaked")
    _require(text.startswith("backup smoke failed\n"), "error mismatch")
    _require(DUMP_KEY + "\n" in text, "dump key missing")
    _require(JSON_KEY + "\n" in text, "json key missing")
    listed = [
        line
        for line in text.splitlines()
        if line.startswith("logical/")
    ]
    _require(listed == [DUMP_KEY, JSON_KEY], "unexpected keys")


@pytest.mark.parametrize(
    "mode",
    ["after-create", "second-object", "final"],
)
def test_partial_failure_prints_both_keys_without_deleting(mode):
    store = StageStore(mode)
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(
        _environ(),
        client_factory=lambda **kwargs: object(),
        store_factory=lambda client, bucket: store,
        id_factory=lambda: BACKUP_ID,
        stdout=stdout,
        stderr=stderr,
    )
    _require(code == 1, "exit mismatch")
    _require(stdout.getvalue() == "", "stdout mismatch")
    _assert_failure_keys(stderr.getvalue())
    _require(store.deleted is False, "delete called")
    _require(
        not any(call[0] == "delete" for call in store.calls),
        "delete recorded",
    )
    if mode == "after-create":
        _require(store.creates == 1, "first create missing")
        _require(DUMP_KEY in store.objects, "dump missing")
        _require(JSON_KEY not in store.objects, "json written early")
    elif mode == "second-object":
        _require(DUMP_KEY in store.objects, "dump missing")
        _require(JSON_KEY not in store.objects, "json written")
    else:
        _require(DUMP_KEY in store.objects, "dump missing")
        _require(JSON_KEY in store.objects, "json missing")


def test_client_construction_failure_does_not_list_keys():
    def factory(**kwargs):
        raise RuntimeError(SECRET + " " + ENDPOINT + " " + BUCKET)

    stderr = io.StringIO()
    code = main(
        _environ(),
        client_factory=factory,
        stderr=stderr,
        stdout=io.StringIO(),
    )
    text = stderr.getvalue()
    _require(code == 1, "exit mismatch")
    _require(text == "backup smoke configuration is invalid\n", "message mismatch")
    _require("logical/daily/" not in text, "keys listed")
    _require(SECRET not in text, "secret leaked")
    _require(BUCKET not in text, "bucket leaked")
