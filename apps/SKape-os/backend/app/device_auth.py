from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.device_credential import DeviceCredential
from app.services.device_auth import verify_device_secret


def get_authenticated_device(
    x_device_id: str = Header(...),
    x_device_secret: str = Header(...),
    db: Session = Depends(get_db),
) -> Device:

    device = (
        db.query(Device)
        .filter(Device.device_id == x_device_id)
        .first()
    )

    if device is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid device credentials",
        )

    if not device.is_active:
        raise HTTPException(
            status_code=403,
            detail="Device is inactive",
        )

    credential = (
        db.query(DeviceCredential)
        .filter(
            DeviceCredential.device_id == device.id,
            DeviceCredential.is_active.is_(True),
        )
        .first()
    )

    if credential is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid device credentials",
        )

    if not verify_device_secret(
        x_device_secret,
        credential.credential_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid device credentials",
        )

    credential.last_used_at = datetime.now(timezone.utc)

    db.commit()

    return device


def verify_device_matches(
    device: Device,
    expected_device_id: int,
) -> Device:

    if device.id != expected_device_id:
        raise HTTPException(
            status_code=403,
            detail="Device credential does not match target device",
        )

    return device