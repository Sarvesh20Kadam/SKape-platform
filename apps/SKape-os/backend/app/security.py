import time
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.env_config import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

SUPPORTED_JWT_ALGORITHM = "HS256"
MIN_SIGNING_SECRET_LENGTH = 32
MIN_PASSWORD_LENGTH = 8
PASSWORD_TOO_SHORT = (
    "Password must contain at least 8 characters."
)
# Each failed login pays this delay, including bcrypt time.
# It slows online guessing. It is not an account lockout and
# does not coordinate attempts across processes or workers.
LOGIN_FAILURE_DELAY_SECONDS = 0.4
_REJECTED_SECRETS = frozenset(
    {
        "secret",
        "changeme",
        "password",
        "none",
        "test-secret",
    }
)


def validate_signing_configuration(
    secret,
    algorithm,
) -> None:
    """Reject missing, short, placeholder, or non-HS256 JWT settings."""

    if algorithm != SUPPORTED_JWT_ALGORITHM:
        raise RuntimeError(
            "JWT algorithm must be HS256."
        )

    if (
        not isinstance(secret, str)
        or len(secret) < MIN_SIGNING_SECRET_LENGTH
        or secret.strip().lower() in _REJECTED_SECRETS
    ):
        raise RuntimeError(
            "JWT signing secret is missing or too short."
        )


def validate_password_length(password: str) -> None:
    if (
        not isinstance(password, str)
        or len(password) < MIN_PASSWORD_LENGTH
    ):
        raise ValueError(PASSWORD_TOO_SHORT)


def wait_for_login_failure(started: float) -> None:
    remaining = LOGIN_FAILURE_DELAY_SECONDS - (
        time.monotonic() - started
    )
    if remaining > 0:
        time.sleep(remaining)


validate_signing_configuration(SECRET_KEY, ALGORITHM)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(data: dict) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    to_encode.update(
        {
            "exp": expire,
        }
    )

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def verify_token(token: str):
    """
    Verify a JWT and return its validated payload.

    JWT signature and expiration are validated by python-jose.
    Required application claims are validated explicitly.
    """

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[SUPPORTED_JWT_ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "require_exp": True,
            },
        )

    except JWTError:
        return None

    subject = payload.get("sub")
    role = payload.get("role")

    if not isinstance(subject, str) or not subject.strip():
        return None

    if not isinstance(role, str) or not role.strip():
        return None

    return payload