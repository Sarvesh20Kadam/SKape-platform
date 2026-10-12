"""Adapt an injected S3 client to the backup object-store protocol.

The wrapper implements ``head``, ``get``, and conditional ``put`` for
``backup.r2``. The caller supplies the client. ``create_r2_client`` is
the only constructor. It requires an explicit endpoint, region, access
key, and secret, then builds one S3 client with those credentials and
the verified configuration. It does not read the process environment,
discover ambient credentials, create a bucket, send a request, or
delete an object.

``head`` returns :class:`backup.r2.ObjectInfo` or ``None`` when the
service reports that the key is absent. A forbidden response is not
absence. ``get`` returns ``(body, ObjectInfo)`` and closes the response
body, including when the read is short or fails. ``put`` sends exactly
one precondition: ``IfNoneMatch`` of ``*``, or ``IfMatch`` set to the
quoted ETag observed earlier. A failed precondition raises
:class:`backup.r2.StorePreconditionError`.

ETags are concurrency tokens. The wrapper keeps the surrounding quotes
and rejects a weak or unquoted token. ``configure_r2_client`` names the
R2 endpoint, explicit credentials, and client settings. It does not
create a client, read the process environment, or use instance
metadata.

``config_options`` is the mapping ``create_r2_client`` passes to its
configuration object: signature version ``s3v4``, path-style
addressing, checksum calculation and validation of ``when_required``,
a finite connect timeout, a finite read timeout, and a bounded
standard-mode retry budget. That retry mode repeats the same request,
so ``IfMatch`` and ``IfNoneMatch`` remain on every attempt. This
wrapper calls the injected client once and does not build another put
without its precondition.

A download is rejected before it is read when ``ContentLength`` is
missing, not a whole number, or larger than 5 GiB. Five GiB is the
single ``PutObject`` maximum, and this phase holds the object in
memory. A response body that defines ``close`` is closed after a
successful read and after every rejection.
"""

import re

from backup.errors import BackupError
from backup.r2 import ObjectInfo, StorePreconditionError


_READ_CHUNK = 65536
_ACCOUNT_ID = re.compile(r"^[0-9a-f]{32}$")
_BUCKET = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
_ACCESS_KEY_ID = re.compile(r"^[A-Za-z0-9]{16,128}$")
_SECRET_ACCESS_KEY = re.compile(r"^[A-Za-z0-9/+=]{32,256}$")
_OBJECT_KEY = re.compile(
    r"^logical/(?:latest\.json|(?:daily|weekly|monthly)/"
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}\.(?:dump|json))$"
)
_QUOTED_ETAG = re.compile(r'"[0-9A-Fa-f]{32}(?:-[1-9][0-9]{0,6})?"')
_MISSING = {"404", "NoSuchKey", "NotFound"}
_FORBIDDEN = {"403", "AccessDenied", "Forbidden"}
_PRECONDITION = {"412", "PreconditionFailed"}
_ENDPOINT_SUFFIX = ".r2.cloudflarestorage.com"
_ENDPOINT_URL = re.compile(
    r"^https://[0-9a-f]{32}\.r2\.cloudflarestorage\.com$"
)
_REGION_NAME = "auto"
_REGION = re.compile(r"^auto$")
_SIGNATURE_VERSION = "s3v4"
_SERVICE_NAME = "s3"
_ADDRESSING_STYLE = "path"
_CHECKSUM_MODE = "when_required"
_RETRY_MODE = "standard"
MAX_OBJECT_BYTES = 5 * 1024 * 1024 * 1024
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 3


def _store_failed():
    raise BackupError("backup object store failed")


def _precondition_failed():
    raise StorePreconditionError("backup publication precondition failed")


def _config_failed():
    raise BackupError("backup object store configuration is invalid")


def _require_text(value, pattern, fail):
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        fail()
    return value


def _quoted_etag(value):
    if not isinstance(value, str) or _QUOTED_ETAG.fullmatch(value) is None:
        _store_failed()
    return value


def _require_key(key):
    if not isinstance(key, str) or _OBJECT_KEY.fullmatch(key) is None:
        _store_failed()
    return key


def _require_body(body):
    if not isinstance(body, bytes) or not body:
        _store_failed()
    if len(body) > MAX_OBJECT_BYTES:
        _store_failed()
    return body


def _require_size(size):
    """Accept a download size before any body byte is read."""

    if isinstance(size, bool) or not isinstance(size, int):
        _store_failed()
    if size < 0 or size > MAX_OBJECT_BYTES:
        _store_failed()
    return size


def _status_and_code(exc):
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return None, None
    error = response.get("Error")
    meta = response.get("ResponseMetadata")
    if not isinstance(error, dict) or not isinstance(meta, dict):
        return None, None
    status = meta.get("HTTPStatusCode")
    code = error.get("Code")
    if isinstance(status, bool) or not isinstance(status, int):
        return None, None
    if not isinstance(code, str):
        return None, None
    return status, code


def _failure_kind(exc):
    """Classify a client error without reading its message."""

    status, code = _status_and_code(exc)
    if status == 404 and code in _MISSING:
        return "missing"
    if status == 403 and code in _FORBIDDEN:
        return "forbidden"
    if status == 412 and code in _PRECONDITION:
        return "precondition"
    return "error"


def _info_from_response(response, *, size=None):
    if not isinstance(response, dict):
        _store_failed()
    etag = _quoted_etag(response.get("ETag"))
    reported = response.get("ContentLength")
    if size is None:
        size = reported
    elif "ContentLength" in response and reported != size:
        _store_failed()
    return ObjectInfo(_require_size(size), etag)


def _close_if_possible(body):
    """Close ``body`` when it has ``close``.

    A missing body or a missing ``close`` method is left untouched.
    ``False`` means ``close`` was called and raised.
    """

    if body is None:
        return True
    close = getattr(body, "close", None)
    if not callable(close):
        return True
    try:
        close()
    except Exception:
        return False
    return True


def _read_exact(body, size):
    size = _require_size(size)
    remaining = size
    chunks = []
    while remaining:
        amt = remaining if remaining < _READ_CHUNK else _READ_CHUNK
        chunk = body.read(amt)
        if not isinstance(chunk, (bytes, bytearray)) or not chunk:
            _store_failed()
        if len(chunk) > amt:
            _store_failed()
        chunks.append(bytes(chunk))
        remaining -= len(chunk)
    extra = body.read(1)
    if not isinstance(extra, (bytes, bytearray)) or extra:
        _store_failed()
    return b"".join(chunks)


class R2ClientConfiguration:
    """Endpoint and signature settings for one injected S3 client.

    The secret is available to the caller that constructs the client.
    ``repr`` does not include it.
    """

    def __init__(
        self,
        *,
        service_name,
        endpoint_url,
        region_name,
        bucket,
        access_key_id,
        secret_access_key,
        signature_version,
        addressing_style,
        request_checksum_calculation,
        response_checksum_validation,
        connect_timeout_seconds,
        read_timeout_seconds,
        max_attempts,
        retry_mode,
    ):
        self._service_name = service_name
        self._endpoint_url = endpoint_url
        self._region_name = region_name
        self._bucket = bucket
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._signature_version = signature_version
        self._addressing_style = addressing_style
        self._request_checksum_calculation = request_checksum_calculation
        self._response_checksum_validation = response_checksum_validation
        self._connect_timeout_seconds = connect_timeout_seconds
        self._read_timeout_seconds = read_timeout_seconds
        self._max_attempts = max_attempts
        self._retry_mode = retry_mode

    def __repr__(self):
        return "R2ClientConfiguration()"

    @property
    def service_name(self):
        return self._service_name

    @property
    def endpoint_url(self):
        return self._endpoint_url

    @property
    def region_name(self):
        return self._region_name

    @property
    def bucket(self):
        return self._bucket

    @property
    def access_key_id(self):
        return self._access_key_id

    @property
    def secret_access_key(self):
        return self._secret_access_key

    @property
    def signature_version(self):
        return self._signature_version

    @property
    def addressing_style(self):
        return self._addressing_style

    @property
    def request_checksum_calculation(self):
        return self._request_checksum_calculation

    @property
    def response_checksum_validation(self):
        return self._response_checksum_validation

    @property
    def connect_timeout_seconds(self):
        return self._connect_timeout_seconds

    @property
    def read_timeout_seconds(self):
        return self._read_timeout_seconds

    @property
    def max_attempts(self):
        return self._max_attempts

    @property
    def retry_mode(self):
        return self._retry_mode

    def config_options(self):
        """Return S3 client settings with no credentials and no endpoint.

        ``create_r2_client`` passes this mapping to its configuration
        object and passes :attr:`access_key_id` and
        :attr:`secret_access_key` separately. ``retries.mode`` is
        ``standard``, which repeats the same request. Conditional
        headers therefore stay on each bounded attempt. This method
        does not import a client library or open a connection.
        """

        return _verified_config_options(
            signature_version=self._signature_version,
            connect_timeout_seconds=self._connect_timeout_seconds,
            read_timeout_seconds=self._read_timeout_seconds,
            max_attempts=self._max_attempts,
            retry_mode=self._retry_mode,
            addressing_style=self._addressing_style,
            request_checksum_calculation=self._request_checksum_calculation,
            response_checksum_validation=(
                self._response_checksum_validation
            ),
        )


def _verified_config_options(
    *,
    signature_version,
    connect_timeout_seconds,
    read_timeout_seconds,
    max_attempts,
    retry_mode,
    addressing_style,
    request_checksum_calculation,
    response_checksum_validation,
):
    return {
        "signature_version": signature_version,
        "connect_timeout": connect_timeout_seconds,
        "read_timeout": read_timeout_seconds,
        "retries": {
            "max_attempts": max_attempts,
            "mode": retry_mode,
        },
        "s3": {"addressing_style": addressing_style},
        "request_checksum_calculation": request_checksum_calculation,
        "response_checksum_validation": response_checksum_validation,
    }


def _load_s3_client_builder():
    """Import the S3 client library when a client is constructed."""

    import boto3
    from botocore.config import Config
    from botocore.session import Session

    return boto3, Config, Session


def configure_r2_client(
    *,
    account_id,
    bucket,
    access_key_id,
    secret_access_key,
):
    """Return R2 client settings. This does not construct a client."""

    account_id = _require_text(account_id, _ACCOUNT_ID, _config_failed)
    bucket = _require_text(bucket, _BUCKET, _config_failed)
    access_key_id = _require_text(
        access_key_id,
        _ACCESS_KEY_ID,
        _config_failed,
    )
    secret_access_key = _require_text(
        secret_access_key,
        _SECRET_ACCESS_KEY,
        _config_failed,
    )
    return R2ClientConfiguration(
        service_name=_SERVICE_NAME,
        endpoint_url="https://%s%s" % (account_id, _ENDPOINT_SUFFIX),
        region_name=_REGION_NAME,
        bucket=bucket,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        signature_version=_SIGNATURE_VERSION,
        addressing_style=_ADDRESSING_STYLE,
        request_checksum_calculation=_CHECKSUM_MODE,
        response_checksum_validation=_CHECKSUM_MODE,
        connect_timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        read_timeout_seconds=READ_TIMEOUT_SECONDS,
        max_attempts=MAX_ATTEMPTS,
        retry_mode=_RETRY_MODE,
    )


def create_r2_client(
    *,
    endpoint_url,
    region_name,
    access_key_id,
    secret_access_key,
):
    """Construct one S3 client from explicit credentials.

    ``endpoint_url``, ``region_name``, ``access_key_id``, and
    ``secret_access_key`` are required. The client uses a new session
    and the verified configuration. This does not read the process
    environment, load a profile, create a bucket, or send a request.
    """

    endpoint_url = _require_text(endpoint_url, _ENDPOINT_URL, _config_failed)
    region_name = _require_text(region_name, _REGION, _config_failed)
    access_key_id = _require_text(
        access_key_id,
        _ACCESS_KEY_ID,
        _config_failed,
    )
    secret_access_key = _require_text(
        secret_access_key,
        _SECRET_ACCESS_KEY,
        _config_failed,
    )
    options = _verified_config_options(
        signature_version=_SIGNATURE_VERSION,
        connect_timeout_seconds=CONNECT_TIMEOUT_SECONDS,
        read_timeout_seconds=READ_TIMEOUT_SECONDS,
        max_attempts=MAX_ATTEMPTS,
        retry_mode=_RETRY_MODE,
        addressing_style=_ADDRESSING_STYLE,
        request_checksum_calculation=_CHECKSUM_MODE,
        response_checksum_validation=_CHECKSUM_MODE,
    )
    failed = False
    client = None
    try:
        boto3, config_type, session_type = _load_s3_client_builder()
        botocore_session = session_type()
        bound = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
            botocore_session=botocore_session,
        )
        client = bound.client(
            _SERVICE_NAME,
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=config_type(**options),
        )
    except Exception:
        failed = True
        client = None
    if failed or client is None:
        _config_failed()
    return client


class R2Client:
    """``head``, ``get``, and conditional ``put`` over an injected client."""

    def __init__(self, client, bucket):
        if client is None:
            _store_failed()
        self._client = client
        self._bucket = _require_text(bucket, _BUCKET, _store_failed)

    def head(self, key):
        key = _require_key(key)
        outcome = "ok"
        response = None
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            outcome = _failure_kind(exc)
        if outcome == "missing":
            return None
        if outcome == "precondition":
            _precondition_failed()
        if outcome != "ok":
            _store_failed()
        return _info_from_response(response)

    def get(self, key):
        key = _require_key(key)
        outcome = "ok"
        response = None
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            outcome = _failure_kind(exc)
        if outcome == "precondition":
            _precondition_failed()
        if outcome != "ok":
            _store_failed()
        body = response.get("Body") if isinstance(response, dict) else None
        payload = None
        info = None
        failed = True
        try:
            readable = callable(getattr(body, "read", None))
            closable = callable(getattr(body, "close", None))
            if isinstance(response, dict) and readable and closable:
                info = _info_from_response(response)
                payload = _read_exact(body, info.size)
                failed = False
        except Exception:
            failed = True
            payload = None
            info = None
        if not _close_if_possible(body):
            failed = True
            payload = None
            info = None
        if failed or payload is None or info is None:
            _store_failed()
        return payload, info

    def put(self, key, body, *, if_match=None, if_none_match=None):
        key = _require_key(key)
        payload = _require_body(body)
        kwargs = {"Bucket": self._bucket, "Key": key, "Body": payload}
        if if_match is not None and if_none_match is None:
            kwargs["IfMatch"] = _quoted_etag(if_match)
        elif if_none_match == "*" and if_match is None:
            kwargs["IfNoneMatch"] = "*"
        else:
            _store_failed()
        outcome = "ok"
        response = None
        try:
            response = self._client.put_object(**kwargs)
        except Exception as exc:
            outcome = _failure_kind(exc)
        if outcome == "precondition":
            _precondition_failed()
        if outcome != "ok":
            _store_failed()
        return _info_from_response(response, size=len(payload))
