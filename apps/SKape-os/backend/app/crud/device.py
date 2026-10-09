from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.crud.activity import log_activity
from app.models.device import Device
from app.models.asset import Asset
from app.models.alert import Alert
from app.schemas.device import DeviceCreate, DeviceUpdate


def _validate_asset(
    db: Session,
    asset_id: int | None,
    organization_id: int,
):
    if asset_id is None:
        return

    asset = (
        db.query(Asset)
        .filter(
            Asset.id == asset_id,
            Asset.organization_id == organization_id,
            Asset.is_active.is_(True),
        )
        .first()
    )

    if asset is None:
        raise ValueError(
            "Asset not found in this organization."
        )


def create_device(
    db: Session,
    device: DeviceCreate,
    organization_id: int,
    user_id: int,
):
    # -------------------------------------------------
    # Validate asset
    # -------------------------------------------------

    _validate_asset(
        db=db,
        asset_id=device.asset_id,
        organization_id=organization_id,
    )

    # -------------------------------------------------
    # Device ID must be globally unique
    # -------------------------------------------------

    existing_device = (
        db.query(Device)
        .filter(
            Device.device_id == device.device_id,
        )
        .first()
    )

    if existing_device is not None:
        raise ValueError(
            "Device ID already exists"
        )

    # -------------------------------------------------
    # Create device
    # -------------------------------------------------

    db_device = Device(
        device_id=device.device_id,
        name=device.name.strip(),
        device_type=device.device_type.strip(),
        status=device.status,
        organization_id=organization_id,
        asset_id=device.asset_id,
        is_active=True,
    )

    db.add(db_device)

    try:
        db.flush()

        log_activity(
            db=db,
            action="created",
            entity="device",
            entity_id=db_device.id,
            user_id=user_id,
            organization_id=organization_id,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(db_device)

    return db_device


def get_devices(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10,
):
    return (
        db.query(Device)
        .filter(
            Device.organization_id == organization_id,
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_device_by_id(
    db: Session,
    device_id: int,
    organization_id: int,
):
    return (
        db.query(Device)
        .filter(
            Device.id == device_id,
            Device.organization_id == organization_id,
        )
        .first()
    )


def update_device(
    db: Session,
    device_id: int,
    organization_id: int,
    user_id: int,
    updated_device: DeviceUpdate,
):
    device = get_device_by_id(
        db,
        device_id,
        organization_id,
    )

    if device is None:
        return None

    update_data = updated_device.model_dump(
        exclude_unset=True,
    )

    # -------------------------------------------------
    # Validate asset if assignment changes
    # -------------------------------------------------

    if "asset_id" in update_data:
        _validate_asset(
            db=db,
            asset_id=update_data["asset_id"],
            organization_id=organization_id,
        )

    # -------------------------------------------------
    # Apply updates
    # -------------------------------------------------

    for key, value in update_data.items():
        if isinstance(value, str):
            value = value.strip()

        setattr(device, key, value)

    try:
        db.flush()

        log_activity(
            db=db,
            action="updated",
            entity="device",
            entity_id=device.id,
            user_id=user_id,
            organization_id=organization_id,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(device)

    return device


def delete_device(
    db: Session,
    device_id: int,
    organization_id: int,
    user_id: int,
):
    device = get_device_by_id(
        db,
        device_id,
        organization_id,
    )

    if device is None:
        return None

    deleted_device_id = device.id
    snapshot = SimpleNamespace(
        id=device.id,
        device_id=device.device_id,
        name=device.name,
        device_type=device.device_type,
        status=device.status,
        organization_id=device.organization_id,
        asset_id=device.asset_id,
        last_seen_at=device.last_seen_at,
        is_active=device.is_active,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )

    try:
        log_activity(
            db=db,
            action="deleted",
            entity="device",
            entity_id=deleted_device_id,
            user_id=user_id,
            organization_id=organization_id,
        )

        db.delete(device)
        db.commit()

    except Exception:
        db.rollback()
        raise

    return snapshot


def heartbeat_device(
    db: Session,
    device_id: str,
):
    device = (
        db.query(Device)
        .filter(
            Device.device_id == device_id,
        )
        .first()
    )

    if device is None:
        return None

    was_offline = device.status == "offline"

    device.status = "online"
    device.last_seen_at = func.now()
    device.is_active = True

    db.flush()

    if was_offline:
        active_alerts = (
            db.query(Alert)
            .filter(
                Alert.device_id == device.id,
                Alert.alert_type == "device_offline",
                Alert.is_resolved.is_(False),
            )
            .all()
        )

        for alert in active_alerts:
            alert.is_resolved = True
            alert.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(device)

    return device



def mark_stale_devices_offline(
    db: Session,
    timeout_seconds: int = 30,
):
    now = datetime.now(timezone.utc)

    online_devices = (
        db.query(Device)
        .filter(
            Device.status == "online",
            Device.last_seen_at.isnot(None),
        )
        .all()
    )

    stale_devices = []

    for device in online_devices:
        last_seen = device.last_seen_at

        if last_seen is None:
            continue

        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(
                tzinfo=timezone.utc
            )

        age_seconds = (
            now - last_seen
        ).total_seconds()

        if age_seconds > timeout_seconds:
            device.status = "offline"
            stale_devices.append(device)

    # Transaction ownership belongs to the caller.
    # The caller creates alerts and commits all changes.
    return stale_devices
