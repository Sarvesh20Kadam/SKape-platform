
import asyncio

from app.database import SessionLocal
from app.crud.device import mark_stale_devices_offline
from app.crud.alert import create_alert


CHECK_INTERVAL_SECONDS = 10
DEVICE_TIMEOUT_SECONDS = 30


async def device_monitor():
    print("[DEVICE MONITOR] Started")

    while True:
        db = SessionLocal()

        try:
            stale_devices = mark_stale_devices_offline(
                db=db,
                timeout_seconds=DEVICE_TIMEOUT_SECONDS,
            )

            for device in stale_devices:
                alert, created = create_alert(
                    db=db,
                    device_id=device.id,
                    organization_id=device.organization_id,
                    severity="critical",
                    alert_type="device_offline",
                    title="Device Offline",
                    message=(
                        f"Device {device.device_id} has stopped "
                        f"sending telemetry and is considered offline."
                    ),
                )

                if created:
                    print(
                        f"[DEVICE MONITOR] "
                        f"{device.device_id} marked OFFLINE; "
                        f"alert {alert.id} created"
                    )

            # Commit device status changes and alerts together.
            db.commit()

        except Exception as error:
            db.rollback()
            print(f"[DEVICE MONITOR] Error: {error}")

        finally:
            db.close()

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
