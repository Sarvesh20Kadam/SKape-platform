"""Offline checks for the injected R2 client wrapper.

Most clients are fake. One test builds a local boto3 client and does
not send a request. These tests do not contact Cloudflare, open a
network connection, or run PostgreSQL.
"""

import hashlib
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.schema_revision import expected_schema_revisions
from backup.errors import BackupError
from backup.r2 import ObjectInfo, StorePreconditionError, publish_remote_backup
from backup.r2_client import (
    CONNECT_TIMEOUT_SECONDS,
    MAX_ATTEMPTS,
    MAX_OBJECT_BYTES,
    READ_TIMEOUT_SECONDS,
    R2Client,
    configure_r2_client,
    create_r2_client,
)


HEADS = expected_schema_revisions()
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
DUMP = b"PGDMPsample"
DIGEST = hashlib.sha256(DUMP).hexdigest()
BUCKET = "skape-backups"
ACCOUNT_ID = "a" * 32
ACCESS_KEY_ID = "b" * 32
SECRET = "c" * 64
KEY = "logical/latest.json"
ETAG = '"0123456789abcdef0123456789abcdef"'
URL = "https://account.r2.cloudflarestorage.com/bucket?X-Amz-Signature=" + SECRET


class FakeClientError(Exception):
    """Client failure whose response message is not safe to surface."""

    def __init__(self, status, code):
        super().__init__(URL)
        self.response = {
            "Error": {"Code": code, "Message": SECRET + " " + URL},
            "ResponseMetadata": {"HTTPStatusCode": status},
        }


class Stream:
    """Byte stream that records closure."""

    def __init__(self, chunks, *, error=None, ignore_limit=False):
        self._chunks = list(chunks)
        self._error = error
        self._ignore_limit = ignore_limit
        self.closed = False
        self.close_calls = 0

    def read(self, amt=None):
        if self._error is not None:
            error = self._error
            self._error = None
            raise RuntimeError(error)
        if not self._chunks:
            return b""
        chunk = self._chunks.pop(0)
        if (
            not self._ignore_limit
            and isinstance(amt, int)
            and not isinstance(amt, bool)
            and len(chunk) > amt
        ):
            self._chunks.insert(0, chunk[amt:])
            chunk = chunk[:amt]
        return chunk

    def close(self):
        self.close_calls += 1
        self.closed = True


class FakeS3:
    """Records head, get, and put calls. It has no successful delete."""

    def __init__(self):
        self.calls = []
        self.head_response = {"ContentLength": 4, "ETag": ETAG}
        self.get_response = None
        self.put_response = {"ETag": ETAG}
        self.head_error = None
        self.get_error = None
        self.put_error = None
        self.delete_calls = 0

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        if self.head_error is not None:
            raise self.head_error
        return self.head_response

    def get_object(self, **kwargs):
        self.calls.append(("get_object", kwargs))
        if self.get_error is not None:
            raise self.get_error
        return self.get_response

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))
        if self.put_error is not None:
            raise self.put_error
        return self.put_response

    def delete_object(self, **kwargs):
        self.delete_calls += 1
        raise AssertionError("delete_object was called")


def _client(fake=None, bucket=BUCKET):
    return R2Client(fake if fake is not None else FakeS3(), bucket)


def _assert_safe(caught):
    message = str(caught.value)
    assert message in {
        "backup object store failed",
        "backup object store configuration is invalid",
        "backup publication precondition failed",
    }
    assert SECRET not in message
    assert "https://" not in message
    assert "X-Amz-Signature" not in message
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_put_sends_exactly_one_conditional_header():
    fake = FakeS3()
    store = _client(fake)
    created = store.put(KEY, b"body", if_none_match="*")
    assert isinstance(created, ObjectInfo)
    assert created.etag == ETAG
    create_call = fake.calls[-1][1]
    assert create_call["Bucket"] == BUCKET
    assert create_call["Key"] == KEY
    assert create_call["Body"] == b"body"
    assert create_call["IfNoneMatch"] == "*"
    assert "IfMatch" not in create_call

    replaced = store.put(KEY, b"next", if_match=ETAG)
    assert replaced.etag == ETAG
    replace_call = fake.calls[-1][1]
    assert replace_call["IfMatch"] == ETAG
    assert "IfNoneMatch" not in replace_call
    assert set(replace_call) == {"Bucket", "Key", "Body", "IfMatch"}

    before = len(fake.calls)
    for kwargs in (
        {},
        {"if_match": ETAG, "if_none_match": "*"},
        {"if_none_match": ETAG},
        {"if_match": "*"},
        {"if_none_match": '"*"'},
    ):
        with pytest.raises(BackupError, match="backup object store failed"):
            store.put(KEY, b"body", **kwargs)
    assert len(fake.calls) == before
    assert fake.delete_calls == 0


def test_quoted_etag_is_preserved_on_read_and_if_match():
    quoted = '"' + ("ab" * 16) + '"'
    multipart = '"0123456789abcdef0123456789abcdef-2"'
    fake = FakeS3()
    fake.head_response = {"ContentLength": 3, "ETag": quoted}
    store = _client(fake)
    info = store.head(KEY)
    assert info.size == 3
    assert info.etag == quoted
    assert info.etag.startswith('"') and info.etag.endswith('"')

    fake.put_response = {"ETag": multipart}
    stored = store.put(KEY, b"abc", if_match=quoted)
    assert stored.etag == multipart
    assert fake.calls[-1][1]["IfMatch"] == quoted

    for bad in (
        "ab" * 16,
        'W/"0123456789abcdef0123456789abcdef"',
        '"0123456789abcdef0123456789abcdef" ',
        '""',
        '"*"',
        quoted + quoted,
        None,
        32,
    ):
        fake.head_response = {"ContentLength": 3, "ETag": bad}
        before = len(fake.calls)
        with pytest.raises(BackupError, match="backup object store failed") as caught:
            store.head(KEY)
        _assert_safe(caught)
        assert len(fake.calls) == before + 1
        with pytest.raises(BackupError, match="backup object store failed"):
            store.put(KEY, b"abc", if_match=bad)
        assert len(fake.calls) == before + 1
    assert fake.delete_calls == 0


@pytest.mark.parametrize(
    ("status", "code", "missing"),
    [
        (404, "404", True),
        (404, "NoSuchKey", True),
        (404, "NotFound", True),
        (403, "403", False),
        (403, "AccessDenied", False),
        (403, "Forbidden", False),
        (404, "AccessDenied", False),
        (403, "NotFound", False),
        (404, "PreconditionFailed", False),
        (400, "404", False),
    ],
)
def test_missing_object_is_not_confused_with_forbidden(status, code, missing):
    fake = FakeS3()
    fake.head_error = FakeClientError(status, code)
    store = _client(fake)
    if missing:
        assert store.head(KEY) is None
    else:
        with pytest.raises(BackupError, match="backup object store failed") as caught:
            store.head(KEY)
        _assert_safe(caught)
        assert not isinstance(caught.value, StorePreconditionError)


def test_get_does_not_treat_not_found_or_forbidden_as_empty():
    for status, code in ((404, "NoSuchKey"), (403, "AccessDenied")):
        fake = FakeS3()
        fake.get_error = FakeClientError(status, code)
        store = _client(fake)
        with pytest.raises(BackupError, match="backup object store failed") as caught:
            store.get(KEY)
        _assert_safe(caught)
        assert caught.value.__class__ is BackupError


def test_precondition_failure_maps_to_store_precondition_error():
    fake = FakeS3()
    fake.put_error = FakeClientError(412, "PreconditionFailed")
    store = _client(fake)
    with pytest.raises(StorePreconditionError, match="precondition failed") as caught:
        store.put(KEY, b"body", if_none_match="*")
    _assert_safe(caught)

    fake.put_error = FakeClientError(412, "412")
    with pytest.raises(StorePreconditionError):
        store.put(KEY, b"body", if_match=ETAG)

    fake.put_error = FakeClientError(412, "SlowDown")
    with pytest.raises(BackupError, match="backup object store failed") as caught:
        store.put(KEY, b"body", if_match=ETAG)
    assert not isinstance(caught.value, StorePreconditionError)
    _assert_safe(caught)

    fake.head_error = FakeClientError(412, "PreconditionFailed")
    with pytest.raises(StorePreconditionError):
        store.head(KEY)


def test_response_body_is_closed_on_success_and_failure():
    payload = b"abcd"
    success = Stream([payload])
    fake = FakeS3()
    fake.get_response = {
        "Body": success,
        "ContentLength": len(payload),
        "ETag": ETAG,
    }
    store = _client(fake)
    body, info = store.get(KEY)
    assert body == payload
    assert info.size == len(payload)
    assert info.etag == ETAG
    assert success.closed is True
    assert success.close_calls == 1

    exploding = Stream([b"ab"], error=URL)
    fake.get_response = {
        "Body": exploding,
        "ContentLength": 4,
        "ETag": ETAG,
    }
    with pytest.raises(BackupError, match="backup object store failed") as caught:
        store.get(KEY)
    _assert_safe(caught)
    assert exploding.closed is True
    assert exploding.close_calls == 1

    closing_error = Stream([payload])

    def _close():
        closing_error.close_calls += 1
        closing_error.closed = True
        raise RuntimeError(URL)

    closing_error.close = _close
    fake.get_response = {
        "Body": closing_error,
        "ContentLength": len(payload),
        "ETag": ETAG,
    }
    with pytest.raises(BackupError, match="backup object store failed") as caught:
        store.get(KEY)
    _assert_safe(caught)
    assert closing_error.close_calls == 1


def test_short_and_long_reads_fail_closed_and_close_the_body():
    short = Stream([b"abc"])
    fake = FakeS3()
    fake.get_response = {"Body": short, "ContentLength": 4, "ETag": ETAG}
    store = _client(fake)
    with pytest.raises(BackupError, match="backup object store failed") as caught:
        store.get(KEY)
    _assert_safe(caught)
    assert short.closed is True

    extra = Stream([b"abcd", b"e"])
    fake.get_response = {"Body": extra, "ContentLength": 4, "ETag": ETAG}
    with pytest.raises(BackupError, match="backup object store failed"):
        store.get(KEY)
    assert extra.closed is True

    oversized = Stream([b"abcdef"], ignore_limit=True)
    fake.get_response = {"Body": oversized, "ContentLength": 4, "ETag": ETAG}
    with pytest.raises(BackupError, match="backup object store failed"):
        store.get(KEY)
    assert oversized.closed is True

    chunked = Stream([b"ab", b"cd"])
    fake.get_response = {"Body": chunked, "ContentLength": 4, "ETag": ETAG}
    body, info = store.get(KEY)
    assert body == b"abcd"
    assert info.etag == ETAG
    assert chunked.closed is True

    empty_extra = Stream([b""])
    fake.get_response = {"Body": empty_extra, "ContentLength": 0, "ETag": ETAG}
    body, info = store.get(KEY)
    assert body == b""
    assert info.size == 0
    assert empty_extra.closed is True


def test_client_errors_hide_secrets_and_do_not_call_with_a_bad_key():
    fake = FakeS3()

    def _explode(**kwargs):
        raise RuntimeError(URL)

    fake.head_object = _explode
    store = _client(fake)
    with pytest.raises(BackupError, match="backup object store failed") as caught:
        store.head(KEY)
    _assert_safe(caught)

    class Odd:
        def head_object(self, **kwargs):
            raise FakeClientError(500, "InternalError")

    with pytest.raises(BackupError, match="backup object store failed") as caught:
        _client(Odd()).head(KEY)
    _assert_safe(caught)

    before = []
    fake = FakeS3()
    store = _client(fake)
    for key in (
        "logical/hourly/backup.dump",
        "../latest.json",
        "logical/latest.json\n",
        "",
        "logical/daily/../x.dump",
        None,
    ):
        with pytest.raises(BackupError, match="backup object store failed"):
            store.head(key)
    assert fake.calls == before
    with pytest.raises(BackupError, match="backup object store failed"):
        store.put(KEY, "", if_none_match="*")
    with pytest.raises(BackupError, match="backup object store failed"):
        store.put(KEY, b"", if_none_match="*")
    assert fake.calls == []


def test_configuration_names_r2_without_creating_a_client(monkeypatch):
    source = Path(__file__).resolve().parents[1].joinpath(
        "backup", "r2_client.py"
    ).read_text(encoding="utf-8")
    def _refuse_builder():
        raise AssertionError("builder")

    monkeypatch.setattr(
        "backup.r2_client._load_s3_client_builder",
        _refuse_builder,
    )
    config = configure_r2_client(
        account_id=ACCOUNT_ID,
        bucket=BUCKET,
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET,
    )
    assert config.service_name == "s3"
    assert config.endpoint_url == (
        "https://%s.r2.cloudflarestorage.com" % ACCOUNT_ID
    )
    assert config.region_name == "auto"
    assert config.bucket == BUCKET
    assert config.access_key_id == ACCESS_KEY_ID
    assert config.secret_access_key == SECRET
    assert config.signature_version == "s3v4"
    assert config.addressing_style == "path"
    assert config.request_checksum_calculation == "when_required"
    assert config.response_checksum_validation == "when_required"
    assert config.connect_timeout_seconds == CONNECT_TIMEOUT_SECONDS == 10
    assert config.read_timeout_seconds == READ_TIMEOUT_SECONDS == 60
    assert config.max_attempts == MAX_ATTEMPTS == 3
    assert config.retry_mode == "standard"
    options = config.config_options()
    assert options == {
        "signature_version": "s3v4",
        "connect_timeout": 10,
        "read_timeout": 60,
        "retries": {"max_attempts": 3, "mode": "standard"},
        "s3": {"addressing_style": "path"},
        "request_checksum_calculation": "when_required",
        "response_checksum_validation": "when_required",
    }
    assert "aws_access_key_id" not in options
    assert "aws_secret_access_key" not in options
    assert SECRET not in repr(options)
    assert "os.environ" not in source
    assert "boto3.client(" not in source
    assert source.count("import boto3") == 1
    assert source.count("from botocore.session import Session") == 1
    assert SECRET not in repr(config)
    assert ACCESS_KEY_ID not in repr(config)
    assert "https://" not in repr(config)
    with pytest.raises(TypeError):
        configure_r2_client(
            account_id=ACCOUNT_ID,
            bucket=BUCKET,
            access_key_id=ACCESS_KEY_ID,
            secret_access_key=SECRET,
            endpoint_url="https://example.invalid",
        )


def test_configuration_rejects_unsafe_values_without_echoing_them():
    leaked = "LEAKED-SECRET-VALUE-" + ("d" * 32)
    samples = [
        {"account_id": "A" * 32},
        {"account_id": "abcd"},
        {"account_id": ACCOUNT_ID + ".example.invalid"},
        {"bucket": "Skape-Backups"},
        {"bucket": "a"},
        {"bucket": "bucket_name"},
        {"access_key_id": "short"},
        {"access_key_id": ACCESS_KEY_ID + " "},
        {"secret_access_key": leaked},
        {"secret_access_key": SECRET + "\n"},
        {"account_id": None},
    ]
    for override in samples:
        values = {
            "account_id": ACCOUNT_ID,
            "bucket": BUCKET,
            "access_key_id": ACCESS_KEY_ID,
            "secret_access_key": SECRET,
        }
        values.update(override)
        with pytest.raises(
            BackupError,
            match="backup object store configuration is invalid",
        ) as caught:
            configure_r2_client(**values)
        _assert_safe(caught)
        assert leaked not in str(caught.value)


def test_wrapper_does_not_retry_a_conditional_put():
    fake = FakeS3()
    fake.put_error = FakeClientError(500, "InternalError")
    store = _client(fake)
    with pytest.raises(BackupError, match="backup object store failed") as caught:
        store.put(KEY, b"body", if_match=ETAG)
    _assert_safe(caught)
    puts = [call for call in fake.calls if call[0] == "put_object"]
    assert len(puts) == 1
    assert puts[0][1]["IfMatch"] == ETAG
    assert "IfNoneMatch" not in puts[0][1]
    assert configure_r2_client(
        account_id=ACCOUNT_ID,
        bucket=BUCKET,
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET,
    ).max_attempts == 3


def test_oversized_or_invalid_length_is_rejected_before_read():
    class CountingStream(Stream):
        def __init__(self, chunks):
            super().__init__(chunks)
            self.reads = 0

        def read(self, amt=None):
            self.reads += 1
            return super().read(amt)

    store_lengths = (
        MAX_OBJECT_BYTES + 1,
        -1,
        True,
        "4",
        None,
    )
    for length in store_lengths:
        stream = CountingStream([b"abcd"])
        fake = FakeS3()
        response = {"Body": stream, "ETag": ETAG}
        if length is not None:
            response["ContentLength"] = length
        fake.get_response = response
        with pytest.raises(BackupError, match="backup object store failed") as caught:
            _client(fake).get(KEY)
        _assert_safe(caught)
        assert stream.reads == 0
        assert stream.closed is True
        assert stream.close_calls == 1

    fake = FakeS3()
    fake.head_response = {
        "ContentLength": MAX_OBJECT_BYTES + 1,
        "ETag": ETAG,
    }
    with pytest.raises(BackupError, match="backup object store failed") as caught:
        _client(fake).head(KEY)
    _assert_safe(caught)

    fake.head_response = {"ContentLength": MAX_OBJECT_BYTES, "ETag": ETAG}
    info = _client(fake).head(KEY)
    assert info.size == MAX_OBJECT_BYTES
    assert info.etag == ETAG


def test_unsupported_bodies_are_closed_when_close_exists():
    class CloseOnly:
        def __init__(self):
            self.closed = False
            self.close_calls = 0

        def close(self):
            self.close_calls += 1
            self.closed = True

    class ReadOnly:
        def __init__(self):
            self.reads = 0

        def read(self, amt=None):
            self.reads += 1
            return b"abcd"

    close_only = CloseOnly()
    fake = FakeS3()
    fake.get_response = {
        "Body": close_only,
        "ContentLength": 4,
        "ETag": ETAG,
    }
    with pytest.raises(BackupError, match="backup object store failed") as caught:
        _client(fake).get(KEY)
    _assert_safe(caught)
    assert close_only.closed is True
    assert close_only.close_calls == 1

    read_only = ReadOnly()
    fake.get_response = {
        "Body": read_only,
        "ContentLength": 4,
        "ETag": ETAG,
    }
    with pytest.raises(BackupError, match="backup object store failed") as caught:
        _client(fake).get(KEY)
    _assert_safe(caught)
    assert read_only.reads == 0

    class BrokenClose(Stream):
        def close(self):
            self.close_calls += 1
            self.closed = True
            raise RuntimeError(URL)

    broken = BrokenClose([b"abcd"])
    fake.get_response = {
        "Body": broken,
        "ContentLength": 4,
        "ETag": ETAG,
    }
    with pytest.raises(BackupError, match="backup object store failed") as caught:
        _client(fake).get(KEY)
    _assert_safe(caught)
    assert broken.close_calls == 1
    assert KEY not in str(caught.value)


def test_client_has_no_delete_method():
    store = _client()
    source = Path(__file__).resolve().parents[1].joinpath(
        "backup", "r2_client.py"
    ).read_text(encoding="utf-8")
    assert not hasattr(store, "delete")
    assert not hasattr(store, "delete_object")
    assert "def delete" not in source
    assert "delete_object" not in source
    names = [
        name
        for name in ("head", "get", "put", "delete", "delete_object")
        if callable(getattr(store, name, None))
    ]
    assert names == ["head", "get", "put"]
    with pytest.raises(BackupError, match="backup object store failed"):
        R2Client(FakeS3(), "Bad_Bucket")
    with pytest.raises(BackupError, match="backup object store failed"):
        R2Client(None, BUCKET)


class _ConditionalS3:
    """In-memory conditional store with quoted ETags and no delete."""

    def __init__(self):
        self._objects = {}
        self._sequence = 0
        self.calls = []

    def head_object(self, *, Bucket, Key):
        self.calls.append("head_object")
        item = self._objects.get((Bucket, Key))
        if item is None:
            raise FakeClientError(404, "NotFound")
        return {"ContentLength": len(item["body"]), "ETag": item["etag"]}

    def get_object(self, *, Bucket, Key):
        self.calls.append("get_object")
        item = self._objects.get((Bucket, Key))
        if item is None:
            raise FakeClientError(404, "NoSuchKey")
        return {
            "ContentLength": len(item["body"]),
            "ETag": item["etag"],
            "Body": Stream([item["body"]]),
        }

    def put_object(self, *, Bucket, Key, Body, IfMatch=None, IfNoneMatch=None):
        self.calls.append(
            {
                "IfMatch": IfMatch,
                "IfNoneMatch": IfNoneMatch,
            }
        )
        if (IfMatch is None) == (IfNoneMatch is None):
            raise FakeClientError(400, "InvalidRequest")
        current = self._objects.get((Bucket, Key))
        if IfNoneMatch is not None:
            if IfNoneMatch != "*" or current is not None:
                raise FakeClientError(412, "PreconditionFailed")
        elif current is None or current["etag"] != IfMatch:
            raise FakeClientError(412, "PreconditionFailed")
        self._sequence += 1
        etag = '"%032x"' % self._sequence
        self._objects[(Bucket, Key)] = {"body": bytes(Body), "etag": etag}
        return {"ETag": etag}


def test_wrapper_publishes_through_the_existing_protocol(tmp_path):
    fake = _ConditionalS3()
    store = R2Client(fake, BUCKET)
    path = tmp_path / "backup.dump"
    path.write_bytes(DUMP)
    payload = {
        "backup_id": "backup-20261011T120000Z",
        "completed_at": "2026-10-11T12:00:00Z",
        "postgres_major": 16,
        "size_bytes": len(DUMP),
        "sha256": DIGEST,
        "schema_revisions": sorted(HEADS),
        "verification_status": "verified",
    }
    manifest = publish_remote_backup(
        store,
        backup_class="daily",
        dump_path=path,
        payload=payload,
        expected_revisions=HEADS,
        now=NOW,
    )
    assert manifest.backup_id == payload["backup_id"]
    puts = [call for call in fake.calls if isinstance(call, dict)]
    assert puts[0]["IfNoneMatch"] == "*"
    assert puts[0]["IfMatch"] is None
    assert puts[-1]["IfNoneMatch"] == "*"
    assert all("delete" not in str(call) for call in fake.calls)
    assert not hasattr(store, "delete")


ENDPOINT = "https://%s.r2.cloudflarestorage.com" % ACCOUNT_ID


class _FactoryDouble:
    def __init__(self):
        self.botocore_sessions = []
        self.boto3_sessions = []
        self.client_calls = []
        self.service_calls = []
        self.config_calls = []
        self.services = []

    def install(self, monkeypatch):
        recording = self

        class Config:
            def __init__(self, **kwargs):
                recording.config_calls.append(kwargs)
                self.kwargs = kwargs

        class BotocoreSession:
            def __init__(self, *args, **kwargs):
                recording.botocore_sessions.append((args, kwargs))
                self.args = args
                self.kwargs = kwargs

        class Service:
            def __getattr__(self, name):
                def called(*args, **kwargs):
                    recording.service_calls.append(name)
                    raise AssertionError(name)

                return called

        class Bound:
            def __init__(self, **kwargs):
                recording.boto3_sessions.append(kwargs)
                self.kwargs = kwargs
                self.service = Service()

            def client(self, *args, **kwargs):
                recording.client_calls.append((args, kwargs))
                recording.services.append(self.service)
                return self.service

        class Boto3:
            @staticmethod
            def Session(**kwargs):
                return Bound(**kwargs)

        monkeypatch.setattr(
            "backup.r2_client._load_s3_client_builder",
            lambda: (Boto3, Config, BotocoreSession),
        )


def test_factory_passes_explicit_credentials_and_verified_config(
    monkeypatch,
):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "e" * 32)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "f" * 64)
    monkeypatch.setenv("AWS_SESSION_TOKEN", "g" * 40)
    monkeypatch.setenv("AWS_PROFILE", "default")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    double = _FactoryDouble()
    double.install(monkeypatch)

    def _refuse_network(*args, **kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("socket.create_connection", _refuse_network)
    client = create_r2_client(
        endpoint_url=ENDPOINT,
        region_name="auto",
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET,
    )
    assert client is double.services[0]
    assert len(double.botocore_sessions) == 1
    assert double.botocore_sessions[0] == ((), {})
    assert len(double.boto3_sessions) == 1
    assert double.boto3_sessions[0] == {
        "aws_access_key_id": ACCESS_KEY_ID,
        "aws_secret_access_key": SECRET,
        "region_name": "auto",
        "botocore_session": double.boto3_sessions[0]["botocore_session"],
    }
    assert "profile_name" not in double.boto3_sessions[0]
    assert double.boto3_sessions[0]["aws_access_key_id"] != "e" * 32
    assert len(double.client_calls) == 1
    args, kwargs = double.client_calls[0]
    assert args == ("s3",)
    assert kwargs["endpoint_url"] == ENDPOINT
    assert kwargs["region_name"] == "auto"
    assert kwargs["aws_access_key_id"] == ACCESS_KEY_ID
    assert kwargs["aws_secret_access_key"] == SECRET
    assert "aws_session_token" not in kwargs
    expected = configure_r2_client(
        account_id=ACCOUNT_ID,
        bucket=BUCKET,
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET,
    ).config_options()
    assert double.config_calls == [expected]
    assert kwargs["config"].kwargs == expected
    assert SECRET not in repr(kwargs["config"])
    assert double.service_calls == []


def test_factory_rejects_invalid_configuration_before_construction(
    monkeypatch,
):
    double = _FactoryDouble()
    double.install(monkeypatch)
    leaked = "LEAKED-SECRET-VALUE-" + ("d" * 32)
    samples = [
        {"endpoint_url": "http://%s.r2.cloudflarestorage.com" % ACCOUNT_ID},
        {"endpoint_url": ENDPOINT + "/bucket"},
        {"endpoint_url": "https://user:%s@example.invalid" % SECRET},
        {"endpoint_url": None},
        {"region_name": "us-east-1"},
        {"region_name": ""},
        {"region_name": None},
        {"access_key_id": "short"},
        {"secret_access_key": leaked},
    ]
    for override in samples:
        values = {
            "endpoint_url": ENDPOINT,
            "region_name": "auto",
            "access_key_id": ACCESS_KEY_ID,
            "secret_access_key": SECRET,
        }
        values.update(override)
        with pytest.raises(
            BackupError,
            match="backup object store configuration is invalid",
        ) as caught:
            create_r2_client(**values)
        _assert_safe(caught)
        assert leaked not in str(caught.value)
        assert double.botocore_sessions == []
        assert double.client_calls == []
        assert double.service_calls == []


def test_factory_hides_sdk_failures(monkeypatch):
    def _explode():
        raise RuntimeError(SECRET + " " + ENDPOINT)

    monkeypatch.setattr(
        "backup.r2_client._load_s3_client_builder",
        _explode,
    )
    with pytest.raises(
        BackupError,
        match="backup object store configuration is invalid",
    ) as caught:
        create_r2_client(
            endpoint_url=ENDPOINT,
            region_name="auto",
            access_key_id=ACCESS_KEY_ID,
            secret_access_key=SECRET,
        )
    _assert_safe(caught)


def test_factory_requires_explicit_arguments():
    with pytest.raises(TypeError):
        create_r2_client(
            region_name="auto",
            access_key_id=ACCESS_KEY_ID,
            secret_access_key=SECRET,
        )


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _refuse_network(*_args, **_kwargs):
    raise AssertionError("network connection attempted")


def test_real_client_uses_explicit_credentials(monkeypatch, tmp_path):
    pytest.importorskip("boto3")
    profile_access = "d" * 32
    profile_secret = "e" * 64
    profile_token = "h" * 40
    env_access = "i" * 32
    config_file = tmp_path / "config"
    credential_file = tmp_path / "credentials"
    config_file.write_text(
        "[default]\nregion = eu-west-1\n",
        encoding="utf-8",
    )
    credential_file.write_text(
        "[default]\naws_access_key_id = %s\n"
        "aws_secret_access_key = %s\n"
        "aws_session_token = %s\n"
        % (profile_access, profile_secret, profile_token),
        encoding="utf-8",
    )
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(credential_file))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", env_access)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "j" * 64)
    monkeypatch.setenv("AWS_SESSION_TOKEN", "k" * 40)
    monkeypatch.setenv("AWS_PROFILE", "default")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setattr(socket, "create_connection", _refuse_network)
    monkeypatch.setattr(socket.socket, "connect", _refuse_network)

    client = create_r2_client(
        endpoint_url=ENDPOINT,
        region_name="auto",
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET,
    )
    try:
        provider = client._request_signer._credentials
        _require(
            type(provider).__name__ == "Credentials",
            "credential provider missing",
        )
        _require(provider.method == "explicit", "credential method mismatch")
        _require(provider.access_key == ACCESS_KEY_ID, "access key mismatch")
        _require(provider.secret_key == SECRET, "secret key mismatch")
        _require(provider.token is None, "session token present")
        _require(
            provider.access_key != profile_access,
            "profile access key used",
        )
        _require(provider.access_key != env_access, "environment access key used")
        _require(provider.secret_key != profile_secret, "profile secret used")
        _require(client.meta.endpoint_url == ENDPOINT, "endpoint mismatch")
        _require(client.meta.region_name == "auto", "region mismatch")
        _require(
            client.meta.config.signature_version == "s3v4",
            "signature mismatch",
        )
        addressing = (client.meta.config.s3 or {}).get("addressing_style")
        _require(addressing == "path", "addressing style mismatch")
    finally:
        client.close()
