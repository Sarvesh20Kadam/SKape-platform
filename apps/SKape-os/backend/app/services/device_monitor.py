import asyncio

from sqlalchemy import text

from app.database import SessionLocal
from app.crud.device import mark_stale_devices_offline
from app.crud.alert import create_alert


CHECK_INTERVAL_SECONDS = 10
DEVICE_TIMEOUT_SECONDS = 30
# Session-level PostgreSQL advisory lock shared by monitor workers.
# It is a coordination key, not a secret. SQLite has no equivalent and
# continues to run the cycle directly.
MONITOR_ADVISORY_LOCK_KEY = 448294001


def _uses_advisory_lock(db):
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _try_acquire_monitor_lock(db):
    if not _uses_advisory_lock(db):
        return True
    acquired = db.execute(
        text(
            "SELECT pg_try_advisory_lock(CAST(:lock_key AS bigint))"
        ),
        {"lock_key": MONITOR_ADVISORY_LOCK_KEY},
    ).scalar()
    return bool(acquired)


def _release_monitor_lock(db):
    if not _uses_advisory_lock(db):
        return
    db.execute(
        text(
            "SELECT pg_advisory_unlock(CAST(:lock_key AS bigint))"
        ),
        {"lock_key": MONITOR_ADVISORY_LOCK_KEY},
    )


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

    On PostgreSQL, one session-level advisory lock covers the cycle.
    Another worker skips this interval instead of repeating the work.
    The lock is released before the next interval. SQLite runs the
    cycle without that lock.
    """

    if not _try_acquire_monitor_lock(db):
        db.rollback()
        return

    try:
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
    finally:
        _release_monitor_lock(db)


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
