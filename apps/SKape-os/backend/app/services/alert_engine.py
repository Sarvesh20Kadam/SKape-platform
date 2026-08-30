from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.telemetry import DeviceTelemetry
from app.models.alert import Alert


def evaluate_telemetry_alerts(
    db: Session,
    device: Device,
    telemetry: DeviceTelemetry,
) -> list[Alert]:
    alerts: list[Alert] = []

    rules = []

    if telemetry.temperature is not None:
        if telemetry.temperature >= 50:
            rules.append(
                (
                    "critical",
                    "high_temperature",
                    "High Temperature",
                    f"Temperature reached {telemetry.temperature:.2f} °C",
                )
            )

        elif telemetry.temperature >= 40:
            rules.append(
                (
                    "warning",
                    "high_temperature",
                    "Elevated Temperature",
                    f"Temperature reached {telemetry.temperature:.2f} °C",
                )
            )

    if telemetry.sensor_1 is not None and telemetry.sensor_1 >= 90:
        rules.append(
            (
                "warning",
                "sensor_1_threshold",
                "Sensor 1 Threshold",
                f"Sensor 1 reached {telemetry.sensor_1:.2f}",
            )
        )

    if telemetry.sensor_2 is not None and telemetry.sensor_2 >= 8:
        rules.append(
            (
                "warning",
                "sensor_2_threshold",
                "Sensor 2 Threshold",
                f"Sensor 2 reached {telemetry.sensor_2:.2f}",
            )
        )

    if telemetry.sensor_3 is not None and telemetry.sensor_3 >= 150:
        rules.append(
            (
                "warning",
                "sensor_3_threshold",
                "Sensor 3 Threshold",
                f"Sensor 3 reached {telemetry.sensor_3:.2f}",
            )
        )

    active_alerts = (
        db.query(Alert)
        .filter(
            Alert.device_id == device.id,
            Alert.is_resolved.is_(False),
        )
        .all()
    )

    active_by_type = {
        alert.alert_type: alert
        for alert in active_alerts
    }

    current_types = set()

    for (
        severity,
        alert_type,
        title,
        message,
    ) in rules:
        current_types.add(alert_type)

        existing = active_by_type.get(alert_type)

        if existing is not None:
            continue

        alert = Alert(
            device_id=device.id,
            organization_id=device.organization_id,
            severity=severity,
            alert_type=alert_type,
            title=title,
            message=message,
        )

        db.add(alert)
        alerts.append(alert)

    for alert in active_alerts:
        if alert.alert_type not in current_types:
            alert.is_resolved = True

            from datetime import datetime, timezone

            alert.resolved_at = datetime.now(timezone.utc)

    if alerts or active_alerts:
        db.commit()

        for alert in alerts:
            db.refresh(alert)

    return alerts