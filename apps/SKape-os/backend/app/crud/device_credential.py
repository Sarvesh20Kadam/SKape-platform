from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.device_credential import DeviceCredential
from app.services.device_auth import (
    generate_device_secret,
    hash_device_secret,
)


def create_device_credential(
    db: Session,
    device: Device,
):
    """
    Create or rotate the credential for a device.

    A device has exactly one credential row because
    device_credentials.device_id is unique.

    If an active credential already exists, provisioning
    is rejected.

    If a revoked/inactive credential exists, its secret
    is rotated in place.
    """

    existing = (
        db.query(DeviceCredential)
        .filter(
            DeviceCredential.device_id == device.id,
        )
        .first()
    )

    if existing is not None and existing.is_active:
        raise ValueError(
            "An active credential already exists for this device."
        )

    raw_secret = generate_device_secret()
    credential_hash = hash_device_secret(raw_secret)

    if existing is not None:
        # Rotate the existing credential in place.
        existing.credential_hash = credential_hash
        existing.is_active = True
        existing.last_used_at = None
        existing.revoked_at = None

        db.commit()
        db.refresh(existing)

        return existing, raw_secret

    # No credential has ever existed for this device.
    credential = DeviceCredential(
        device_id=device.id,
        credential_hash=credential_hash,
        is_active=True,
    )

    db.add(credential)
    db.commit()
    db.refresh(credential)

    return credential, raw_secret


def revoke_device_credential(
    db: Session,
    device: Device,
):
    """
    Revoke the active credential for a device.

    The credential row is retained so that it can later
    be safely rotated instead of creating a second row.
    """

    credential = (
        db.query(DeviceCredential)
        .filter(
            DeviceCredential.device_id == device.id,
            DeviceCredential.is_active.is_(True),
        )
        .first()
    )

    if credential is None:
        return None

    credential.is_active = False
    credential.revoked_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(credential)

    return credential