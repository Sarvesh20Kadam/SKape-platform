from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.telemetry import DeviceTelemetry
from app.models.device import Device
from app.schemas.telemetry import TelemetryCreate
from app.services.alert_engine import evaluate_telemetry_alerts


def create_telemetry(
    db: Session,
    device: Device,
    telemetry: TelemetryCreate,
):
    now = datetime.now(timezone.utc)

    db_telemetry = DeviceTelemetry(
        device_id=device.id,
        temperature=telemetry.temperature,
        sensor_1=telemetry.sensor_1,
        sensor_2=telemetry.sensor_2,
        sensor_3=telemetry.sensor_3,
        created_at=now,
    )

    db.add(db_telemetry)

    # A valid telemetry packet proves that the device
    # is communicating with SKape OS.
    device.status = "online"
    device.last_seen_at = now
    device.is_active = True

    db.flush()

    evaluate_telemetry_alerts(
        db=db,
        device=device,
        telemetry=db_telemetry,
    )

    db.commit()
    db.refresh(db_telemetry)

    return db_telemetry


def get_latest_telemetry(
    db: Session,
    device: Device,
):
    return (
        db.query(DeviceTelemetry)
        .filter(
            DeviceTelemetry.device_id == device.id,
        )
        .order_by(
            DeviceTelemetry.created_at.desc(),
            DeviceTelemetry.id.desc(),
        )
        .first()
    )


def get_device_telemetry(
    db: Session,
    device: Device,
    limit: int = 50,
):
    return (
        db.query(DeviceTelemetry)
        .filter(
            DeviceTelemetry.device_id == device.id,
        )
        .order_by(
            DeviceTelemetry.created_at.desc(),
            DeviceTelemetry.id.desc(),
        )
        .limit(limit)
        .all()
    )