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

    Health levels:
        healthy  -> device is online and telemetry is fresh
        warning   -> telemetry is becoming stale or sensors are missing
        critical  -> device is offline or telemetry is critically stale
    """

    # --------------------------------------------------------
    # Device connectivity
    # --------------------------------------------------------

    if device.status != "online":
        return {
            "status": "critical",
            "reason": "Device is offline",
        }

    # --------------------------------------------------------
    # Telemetry availability
    # --------------------------------------------------------

    if latest_telemetry is None:
        return {
            "status": "warning",
            "reason": "No telemetry data available",
        }

    # --------------------------------------------------------
    # Telemetry freshness
    # --------------------------------------------------------

    created_at = latest_telemetry.created_at

    if created_at.tzinfo is None:
        created_at = created_at.replace(
            tzinfo=timezone.utc
        )

    now = datetime.now(timezone.utc)

    telemetry_age = (
        now - created_at
    ).total_seconds()

    if telemetry_age >= TELEMETRY_CRITICAL_SECONDS:
        return {
            "status": "critical",
            "reason": "Telemetry data is stale",
        }

    if telemetry_age >= TELEMETRY_WARNING_SECONDS:
        return {
            "status": "warning",
            "reason": "Telemetry data is becoming stale",
        }

    # --------------------------------------------------------
    # Sensor availability
    # --------------------------------------------------------

    sensor_values = [
        latest_telemetry.temperature,
        latest_telemetry.sensor_1,
        latest_telemetry.sensor_2,
        latest_telemetry.sensor_3,
    ]

    missing_sensors = sum(
        value is None
        for value in sensor_values
    )

    if missing_sensors >= 2:
        return {
            "status": "warning",
            "reason": "Multiple sensor readings are unavailable",
        }

    if missing_sensors == 1:
        return {
            "status": "warning",
            "reason": "A sensor reading is unavailable",
        }

    # --------------------------------------------------------
    # Healthy
    # --------------------------------------------------------

    return {
        "status": "healthy",
        "reason": "Device is online and telemetry is healthy",
    }