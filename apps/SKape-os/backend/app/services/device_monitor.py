import asyncio

from app.database import SessionLocal
from app.crud.device import mark_stale_devices_offline
from app.crud.alert import create_alert


CHECK_INTERVAL_SECONDS = 10
DEVICE_TIMEOUT_SECONDS = 30


def run_monitor_cycle(
    db,
    timeout_seconds: int = DEVICE_TIMEOUT_SECONDS,
):
    """
    Mark stale devices offline and record one outage alert.

    Status changes and alerts commit together. Any failure rolls the
    cycle back and is re-raised so the caller can retry from the last
    committed state. Devices that are online without last_seen_at are
    not part of this cycle; a missing timestamp is not treated as an
    outage.
    """

    try:
        stale_devices = mark_stale_devices_offline(
            db=db,
            timeout_seconds=timeout_seconds,
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

        db.commit()

    except Exception:
        db.rollback()
        raise


async def device_monitor():
    print("[DEVICE MONITOR] Started")

    while True:
        db = SessionLocal()

        try:
            run_monitor_cycle(db)

        except Exception as error:
            print(f"[DEVICE MONITOR] Error: {error}")

        finally:
            db.close()

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
