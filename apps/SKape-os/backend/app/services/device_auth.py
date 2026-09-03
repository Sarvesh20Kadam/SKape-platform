import secrets

from app.security import (
    hash_password,
    verify_password,
)


DEVICE_SECRET_BYTES = 32


def generate_device_secret() -> str:
    """
    Generate a cryptographically secure device secret.

    The raw secret is returned only during device provisioning.
    """
    return secrets.token_urlsafe(DEVICE_SECRET_BYTES)


def hash_device_secret(secret: str) -> str:
    """
    Hash a device secret before storing it in the database.
    """
    return hash_password(secret)


def verify_device_secret(
    secret: str,
    credential_hash: str,
) -> bool:
    """
    Verify a presented device secret against its stored hash.
    """
    return verify_password(
        secret,
        credential_hash,
    )