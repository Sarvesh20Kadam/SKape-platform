from datetime import datetime, timezone

from app.models.device import Device
from app.models.telemetry import DeviceTelemetry


TELEMETRY_WARNING_SECONDS = 15
TELEMETRY_CRITICAL_SECONDS = 30


def calculate_device_health(
    device: Device,
    latest_telemetry: DeviceTelemetry | None,
):
    """
    Calculate the current health of a device.
    """

    now = datetime.now(timezone.utc)

    # --------------------------------------------------------
    # Sensor information
    # --------------------------------------------------------

    sensor_values = [
        latest_telemetry.temperature
        if latest_telemetry is not None
        else None,
        latest_telemetry.sensor_1
        if latest_telemetry is not None
        else None,
        latest_telemetry.sensor_2
        if latest_telemetry is not None
        else None,
        latest_telemetry.sensor_3
        if latest_telemetry is not None
        else None,
    ]

    sensors_total = len(sensor_values)
    sensors_available = sum(
        value is not None
        for value in sensor_values
    )

    # --------------------------------------------------------
    # Telemetry timestamp / age
    # --------------------------------------------------------

    telemetry_at = None
    telemetry_age_seconds = None

    if latest_telemetry is not None:
        telemetry_at = latest_telemetry.created_at

        if telemetry_at.tzinfo is None:
            telemetry_at = telemetry_at.replace(
                tzinfo=timezone.utc
            )

        telemetry_age_seconds = max(
            0.0,
            (now - telemetry_at).total_seconds(),
        )

    # --------------------------------------------------------
    # Common response data
    # --------------------------------------------------------

    health_data = {
        "device_status": device.status,
        "last_seen_at": device.last_seen_at,
        "telemetry_at": telemetry_at,
        "telemetry_age_seconds": telemetry_age_seconds,
        "sensors_available": sensors_available,
        "sensors_total": sensors_total,
    }

    # --------------------------------------------------------
    # Device connectivity
    # --------------------------------------------------------

    if device.status != "online":
        return {
            "status": "critical",
            "reason": "Device is offline",
            **health_data,
        }

    # --------------------------------------------------------
    # Telemetry availability
    # --------------------------------------------------------

    if latest_telemetry is None:
        return {
            "status": "warning",
            "reason": "No telemetry data available",
            **health_data,
        }

    # --------------------------------------------------------
    # Telemetry freshness
    # --------------------------------------------------------

    if telemetry_age_seconds >= TELEMETRY_CRITICAL_SECONDS:
        return {
            "status": "critical",
            "reason": "Telemetry data is stale",
            **health_data,
        }

    if telemetry_age_seconds >= TELEMETRY_WARNING_SECONDS:
        return {
            "status": "warning",
            "reason": "Telemetry data is becoming stale",
            **health_data,
        }

    # --------------------------------------------------------
    # Sensor availability
    # --------------------------------------------------------

    if sensors_available <= 2:
        return {
            "status": "warning",
            "reason": "Multiple sensor readings are unavailable",
            **health_data,
        }

    if sensors_available == 3:
        return {
            "status": "warning",
            "reason": "A sensor reading is unavailable",
            **health_data,
        }

    # --------------------------------------------------------
    # Healthy
    # --------------------------------------------------------

    return {
        "status": "healthy",
        "reason": "Device is online and telemetry is healthy",
        **health_data,
    }