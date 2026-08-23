from sqlalchemy.orm import Session

from app.crud.activity import log_activity
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate


def create_device(
    db: Session,
    device: DeviceCreate,
    organization_id: int,
    user_id: int,
):
    existing_device = (
        db.query(Device)
        .filter(
            Device.device_id == device.device_id,
        )
        .first()
    )

    if existing_device is not None:
        raise ValueError("Device ID already exists")

    db_device = Device(
        device_id=device.device_id,
        name=device.name,
        device_type=device.device_type,
        status=device.status,
        organization_id=organization_id,
        asset_id=device.asset_id,
        is_active=True,
    )

    db.add(db_device)
    db.commit()
    db.refresh(db_device)

    log_activity(
        db=db,
        action="created",
        entity="device",
        entity_id=db_device.id,
        user_id=user_id,
        organization_id=organization_id,
    )

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

    for key, value in update_data.items():
        setattr(device, key, value)

    db.commit()
    db.refresh(device)

    log_activity(
        db=db,
        action="updated",
        entity="device",
        entity_id=device.id,
        user_id=user_id,
        organization_id=organization_id,
    )

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

    db.delete(device)
    db.commit()

    log_activity(
        db=db,
        action="deleted",
        entity="device",
        entity_id=deleted_device_id,
        user_id=user_id,
        organization_id=organization_id,
    )

    return device