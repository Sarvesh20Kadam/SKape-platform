from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import update
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.crud.activity import log_activity
from app.models.device import Device
from app.models.asset import Asset
from app.models.alert import Alert
from app.schemas.device import DeviceCreate, DeviceUpdate


def _normalized_status(status):
    if isinstance(status, str):
        return status.strip()
    return status


def _reject_online_without_last_seen(status, last_seen_at):
    """Online means the device has checked in.

    Heartbeat and telemetry are the lifecycle paths that set status
    to online, and both record last_seen_at in the same write. A
    missing timestamp is not an outage and must not be stored as online.
    """

    if (
        _normalized_status(status) == "online"
        and last_seen_at is None
    ):
        raise ValueError(
            "A device cannot be online without a last-seen time."
        )


def _resolve_offline_alerts(db, device):
    active_alerts = (
        db.query(Alert)
        .filter(
            Alert.device_id == device.id,
            Alert.alert_type == "device_offline",
            Alert.is_resolved.is_(False),
        )
        .all()
    )

    resolved_at = datetime.now(timezone.utc)
    for alert in active_alerts:
        alert.is_resolved = True
        alert.resolved_at = resolved_at


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

    status = _normalized_status(device.status)
    _reject_online_without_last_seen(status, None)

    # -------------------------------------------------
    # Create device
    # -------------------------------------------------

    db_device = Device(
        device_id=device.device_id,
        name=device.name.strip(),
        device_type=device.device_type.strip(),
        status=status,
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

    next_status = _normalized_status(
        update_data.get("status", device.status)
    )
    next_seen = (
        update_data["last_seen_at"]
        if "last_seen_at" in update_data
        else device.last_seen_at
    )
    _reject_online_without_last_seen(next_status, next_seen)

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
        .with_for_update()
        .first()
    )

    if device is None:
        return None

    device.status = "online"
    device.last_seen_at = func.now()
    device.is_active = True

    db.flush()

    # Resolve even when the row was already online. A concurrent
    # monitor cycle may have inserted the offline alert after this
    # heartbeat read the previous status.
    _resolve_offline_alerts(db, device)

    db.commit()
    db.refresh(device)

    return device



def mark_stale_devices_offline(
    db: Session,
    timeout_seconds: int = 30,
):
    """
    Mark contacted devices offline when last_seen_at is older than
    timeout_seconds.

    A device becomes online only through heartbeat or telemetry, and
    both of those writes store last_seen_at. An online row with no
    last_seen_at is inconsistent, not stale: this function does not
    change it and does not create an outage for it.

    The transition is one conditional UPDATE. A heartbeat or telemetry
    commit that stored a newer last_seen_at no longer matches, so this
    session cannot overwrite that contact with an older decision.
    When this session has only read so far, its snapshot is closed
    first so the UPDATE observes those commits. The caller commits.
    """

    if not db.new and not db.dirty and not db.deleted:
        db.rollback()

    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=timeout_seconds
    )
    statement = (
        update(Device)
        .where(
            Device.status == "online",
            Device.last_seen_at.isnot(None),
            Device.last_seen_at < cutoff,
        )
        .values(status="offline")
        .returning(Device.id)
    )
    changed_ids = list(db.execute(statement).scalars().all())

    if not changed_ids:
        return []

    for device_id in changed_ids:
        loaded = db.get(Device, device_id)
        if loaded is not None:
            db.expire(loaded)

    return (
        db.query(Device)
        .filter(Device.id.in_(changed_ids))
        .all()
    )
