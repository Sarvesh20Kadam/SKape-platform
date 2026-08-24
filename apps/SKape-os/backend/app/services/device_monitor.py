import asyncio

from app.database import SessionLocal
from app.crud.device import mark_stale_devices_offline


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
                print(
                    f"[DEVICE MONITOR] "
                    f"{device.device_id} marked OFFLINE"
                )

        except Exception as error:
            print(
                f"[DEVICE MONITOR] Error: {error}"
            )

        finally:
            db.close()

        await asyncio.sleep(
            CHECK_INTERVAL_SECONDS
        )