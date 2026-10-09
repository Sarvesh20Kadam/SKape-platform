import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.crud.alert import (
    create_alert,
    get_active_device_alert,
)
from app.crud.device import (
    heartbeat_device,
    mark_stale_devices_offline,
    update_device,
)
from app.crud.telemetry import create_telemetry
from app.database import Base
from app.models.alert import Alert
from app.models.device import Device
from app.models.organization import Organization
from app.models.user import User
from app.schemas.device import DeviceUpdate
from app.schemas.telemetry import TelemetryCreate
from app.security import hash_password
from app.services.device_monitor import run_monitor_cycle


PASSWORD = "Correct-horse-1"
ONLINE_REQUIRES_SEEN = (
    "A device cannot be online without a last-seen time."
)


def _migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "f6b1c0a84e22_guard_device_monitor_consistency.py"
    )
    spec = importlib.util.spec_from_file_location(
        "device_monitor_consistency",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def world(db):
    organization = Organization(
        name="Org A",
        slug="org-a",
        is_active=True,
    )
    db.add(organization)
    db.flush()
    owner = User(
        name="owner",
        email="owner@example.com",
        hashed_password=hash_password(PASSWORD),
        role="owner",
        is_active=True,
        organization_id=organization.id,
    )
    db.add(owner)
    db.commit()
    return {
        "org_a": organization.id,
        "owner_id": owner.id,
        "owner": owner.email,
    }


def _device(
    db,
    organization_id,
    device_id,
    status="offline",
    last_seen_at=None,
):
    device = Device(
        device_id=device_id,
        name=device_id,
        device_type="sensor",
        status=status,
        organization_id=organization_id,
        is_active=True,
        last_seen_at=last_seen_at,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def _offline_alert(db, device):
    alert = Alert(
        device_id=device.id,
        organization_id=device.organization_id,
        severity="critical",
        alert_type="device_offline",
        title="Device Offline",
        message="Stopped",
        is_resolved=False,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def _auth(api, email):
    response = api.post(
        "/api/v1/users/login",
        data={
            "username": email,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return {
        "Authorization": (
            f"Bearer {response.json()['access_token']}"
        )
    }


def test_unresolved_device_offline_alert_is_unique(db, world):
    device = _device(db, world["org_a"], "pump-01")
    _offline_alert(db, device)

    duplicate = Alert(
        device_id=device.id,
        organization_id=device.organization_id,
        severity="critical",
        alert_type="device_offline",
        title="Again",
        message="Stopped again",
        is_resolved=False,
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    resolved = Alert(
        device_id=device.id,
        organization_id=device.organization_id,
        severity="critical",
        alert_type="device_offline",
        title="Earlier",
        message="Already recovered",
        is_resolved=True,
        resolved_at=datetime.now(timezone.utc),
    )
    other = Alert(
        device_id=device.id,
        organization_id=device.organization_id,
        severity="warning",
        alert_type="high_temperature",
        title="Hot",
        message="Warm",
        is_resolved=False,
    )
    db.add(resolved)
    db.add(other)
    db.commit()

    stored = (
        db.query(Alert)
        .filter(
            Alert.device_id == device.id,
            Alert.alert_type == "device_offline",
            Alert.is_resolved.is_(False),
        )
        .all()
    )
    assert len(stored) == 1
    assert (
        db.query(Alert)
        .filter(Alert.alert_type == "high_temperature")
        .count()
        == 1
    )


def test_create_alert_keeps_pending_work_when_insert_loses(
    db,
    world,
    monkeypatch,
):
    device = _device(
        db,
        world["org_a"],
        "pump-02",
        status="online",
        last_seen_at=datetime.now(timezone.utc),
    )
    winner, created = create_alert(
        db=db,
        device_id=device.id,
        organization_id=device.organization_id,
        severity="critical",
        alert_type="device_offline",
        title="Device Offline",
        message="First",
    )
    assert created is True
    device.status = "offline"
    db.commit()
    device.name = "Kept name"

    calls = {"count": 0}
    real_lookup = get_active_device_alert

    def hide_first_lookup(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return real_lookup(**kwargs)

    monkeypatch.setattr(
        "app.crud.alert.get_active_device_alert",
        hide_first_lookup,
    )

    loser, created_again = create_alert(
        db=db,
        device_id=device.id,
        organization_id=device.organization_id,
        severity="critical",
        alert_type="device_offline",
        title="Device Offline",
        message="Second",
    )
    assert created_again is False
    assert loser.id == winner.id
    db.commit()

    check_device = db.get(Device, device.id)
    assert check_device.status == "offline"
    assert check_device.name == "Kept name"
    assert (
        db.query(Alert)
        .filter(
            Alert.device_id == device.id,
            Alert.alert_type == "device_offline",
            Alert.is_resolved.is_(False),
        )
        .count()
        == 1
    )


def test_online_without_last_seen_is_rejected_and_not_stale(
    db,
    world,
    session_factory,
):
    device = _device(db, world["org_a"], "pump-03")

    with pytest.raises(ValueError, match=ONLINE_REQUIRES_SEEN):
        update_device(
            db=db,
            device_id=device.id,
            organization_id=world["org_a"],
            user_id=world["owner_id"],
            updated_device=DeviceUpdate(status="online"),
        )

    invalid = Device(
        device_id="pump-04",
        name="Pump 4",
        device_type="sensor",
        status="online",
        organization_id=world["org_a"],
        is_active=True,
        last_seen_at=None,
    )
    db.add(invalid)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.execute(text("PRAGMA ignore_check_constraints = ON"))
    inconsistent = Device(
        device_id="pump-05",
        name="Pump 5",
        device_type="sensor",
        status="online",
        organization_id=world["org_a"],
        is_active=True,
        last_seen_at=None,
    )
    db.add(inconsistent)
    db.commit()
    db.execute(text("PRAGMA ignore_check_constraints = OFF"))

    run_monitor_cycle(db, timeout_seconds=30)

    check = session_factory()
    try:
        stored = check.get(Device, device.id)
        assert stored.status == "offline"
        assert stored.last_seen_at is None
        untouched = (
            check.query(Device)
            .filter(Device.device_id == "pump-05")
            .one()
        )
        assert untouched.status == "online"
        assert untouched.last_seen_at is None
        assert (
            check.query(Alert)
            .filter(Alert.device_id == untouched.id)
            .count()
            == 0
        )
    finally:
        check.close()


def test_update_online_requires_last_seen_on_the_api(api, world):
    headers = _auth(api, world["owner"])
    created = api.post(
        "/api/v1/devices/",
        headers=headers,
        json={
            "device_id": "pump-06",
            "name": "Pump 6",
            "device_type": "sensor",
            "status": "online",
        },
    )
    assert created.status_code == 400
    assert created.json()["detail"] == ONLINE_REQUIRES_SEEN

    created = api.post(
        "/api/v1/devices/",
        headers=headers,
        json={
            "device_id": "pump-06",
            "name": "Pump 6",
            "device_type": "sensor",
        },
    )
    assert created.status_code == 200, created.text
    device_pk = created.json()["id"]

    updated = api.put(
        f"/api/v1/devices/{device_pk}",
        headers=headers,
        json={"status": "online"},
    )
    assert updated.status_code == 400
    assert updated.json()["detail"] == ONLINE_REQUIRES_SEEN


def test_heartbeat_does_not_lose_to_a_stale_monitor_read(
    db,
    world,
    session_factory,
):
    seen = datetime.now(timezone.utc) - timedelta(minutes=5)
    device = _device(
        db,
        world["org_a"],
        "pump-07",
        status="online",
        last_seen_at=seen,
    )
    loaded = db.get(Device, device.id)
    assert loaded.status == "online"

    contact = session_factory()
    try:
        heartbeat_device(contact, device.device_id)
    finally:
        contact.close()

    stale = mark_stale_devices_offline(
        db,
        timeout_seconds=30,
    )
    db.commit()
    assert stale == []

    check = session_factory()
    try:
        stored = check.get(Device, device.id)
        assert stored.status == "online"
        last_seen = stored.last_seen_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        assert last_seen > seen
        assert check.query(Alert).count() == 0
    finally:
        check.close()


def test_telemetry_contact_resolves_offline_alert(db, world):
    device = _device(db, world["org_a"], "pump-08", status="offline")
    alert = _offline_alert(db, device)

    create_telemetry(
        db=db,
        device=device,
        telemetry=TelemetryCreate(temperature=21.5),
    )

    check = db.get(Device, device.id)
    stored_alert = db.get(Alert, alert.id)
    assert check.status == "online"
    assert check.last_seen_at is not None
    assert stored_alert.is_resolved is True
    assert stored_alert.resolved_at is not None


def test_failed_monitor_cycle_rolls_back_and_retries(
    db,
    world,
    session_factory,
    monkeypatch,
):
    stale_seen = datetime.now(timezone.utc) - timedelta(minutes=5)
    fresh_seen = datetime.now(timezone.utc)
    stale = _device(
        db,
        world["org_a"],
        "pump-09",
        status="online",
        last_seen_at=stale_seen,
    )
    fresh = _device(
        db,
        world["org_a"],
        "pump-10",
        status="online",
        last_seen_at=fresh_seen,
    )

    def fail_alert(**kwargs):
        raise RuntimeError("monitor failed")

    monkeypatch.setattr(
        "app.services.device_monitor.create_alert",
        fail_alert,
    )

    with pytest.raises(RuntimeError, match="monitor failed"):
        run_monitor_cycle(db, timeout_seconds=30)

    check = session_factory()
    try:
        assert check.get(Device, stale.id).status == "online"
        assert check.get(Device, fresh.id).status == "online"
        assert check.query(Alert).count() == 0
    finally:
        check.close()

    monkeypatch.undo()
    run_monitor_cycle(db, timeout_seconds=30)

    check = session_factory()
    try:
        assert check.get(Device, stale.id).status == "offline"
        assert check.get(Device, fresh.id).status == "online"
        alerts = (
            check.query(Alert)
            .filter(Alert.alert_type == "device_offline")
            .all()
        )
        assert len(alerts) == 1
        assert alerts[0].device_id == stale.id
        assert alerts[0].is_resolved is False
        assert alerts[0].organization_id == world["org_a"]
    finally:
        check.close()


def test_competing_alert_keeps_uncommitted_offline_status(
    db,
    world,
    session_factory,
    monkeypatch,
):
    seen = datetime.now(timezone.utc) - timedelta(minutes=5)
    device = _device(
        db,
        world["org_a"],
        "pump-11",
        status="online",
        last_seen_at=seen,
    )
    device_pk = device.id
    existing = _offline_alert(db, device)
    existing_id = existing.id

    calls = {"count": 0}
    observed = {}
    real_lookup = get_active_device_alert

    def hide_first_lookup(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return real_lookup(**kwargs)

    def observe_pending_status(**kwargs):
        result = create_alert(**kwargs)
        db.expire(db.get(Device, device_pk))
        pending = db.get(Device, device_pk)
        observed["status"] = pending.status
        observed["created"] = result[1]
        observed["alert_id"] = result[0].id
        return result

    monkeypatch.setattr(
        "app.crud.alert.get_active_device_alert",
        hide_first_lookup,
    )
    monkeypatch.setattr(
        "app.services.device_monitor.create_alert",
        observe_pending_status,
    )

    run_monitor_cycle(db, timeout_seconds=30)

    assert calls["count"] == 2
    assert observed["created"] is False
    assert observed["alert_id"] == existing_id
    assert observed["status"] == "offline"

    check = session_factory()
    try:
        stored = check.get(Device, device_pk)
        assert stored.status == "offline"
        last_seen = stored.last_seen_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        assert abs((last_seen - seen).total_seconds()) < 1
        alerts = (
            check.query(Alert)
            .filter(
                Alert.device_id == device_pk,
                Alert.alert_type == "device_offline",
                Alert.is_resolved.is_(False),
            )
            .all()
        )
        assert len(alerts) == 1
        assert alerts[0].id == existing_id
    finally:
        check.close()


def test_migration_refuses_online_device_without_last_seen():
    module = _migration()
    engine = create_engine("sqlite://")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE devices (
                    id INTEGER PRIMARY KEY,
                    device_id VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    last_seen_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE alerts (
                    id INTEGER PRIMARY KEY,
                    device_id INTEGER NOT NULL,
                    alert_type VARCHAR NOT NULL,
                    is_resolved BOOLEAN NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                "INSERT INTO devices (id, device_id, status) "
                "VALUES (1, 'untouched-pump', 'online')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO alerts "
                "(id, device_id, alert_type, is_resolved) "
                "VALUES (1, 1, 'device_offline', 0)"
            )
        )

    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with pytest.raises(
            RuntimeError,
            match="Rows were not changed: untouched-pump",
        ):
            with Operations.context(context):
                module.upgrade()
        connection.rollback()

        index_name = connection.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE name = "
                "'uq_alerts_unresolved_device_offline'"
            )
        ).fetchall()
        assert index_name == []

        table_sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'table' AND name = 'devices'"
            )
        ).scalar()
        assert "ck_devices_online_requires_last_seen" not in table_sql
        assert "last_seen_at IS NOT NULL" not in table_sql

        connection.execute(
            text(
                "INSERT INTO devices (id, device_id, status) "
                "VALUES (2, 'also-missing', 'online')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO alerts "
                "(id, device_id, alert_type, is_resolved) "
                "VALUES (2, 1, 'device_offline', 0)"
            )
        )
        connection.commit()

        original = connection.execute(
            text(
                "SELECT status, last_seen_at FROM devices "
                "WHERE device_id = 'untouched-pump'"
            )
        ).one()
        assert original.status == "online"
        assert original.last_seen_at is None

    engine.dispose()


def test_monitor_migration_rejects_conflicts_then_enforces_them():
    module = _migration()
    engine = create_engine("sqlite://")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE devices (
                    id INTEGER PRIMARY KEY,
                    device_id VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    last_seen_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE alerts (
                    id INTEGER PRIMARY KEY,
                    device_id INTEGER NOT NULL,
                    alert_type VARCHAR NOT NULL,
                    is_resolved BOOLEAN NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO alerts (
                    id, device_id, alert_type, is_resolved
                )
                VALUES
                    (1, 7, 'device_offline', 0),
                    (2, 7, 'device_offline', 0)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO devices (id, device_id, status)
                VALUES (7, 'missing-seen', 'online')
                """
            )
        )

    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with pytest.raises(RuntimeError, match="not deleted or merged"):
            with Operations.context(context):
                module.upgrade()

    clean = create_engine("sqlite://")
    with clean.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE devices (
                    id INTEGER PRIMARY KEY,
                    device_id VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    last_seen_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE alerts (
                    id INTEGER PRIMARY KEY,
                    device_id INTEGER NOT NULL,
                    alert_type VARCHAR NOT NULL,
                    is_resolved BOOLEAN NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                "INSERT INTO devices "
                "(id, device_id, status, last_seen_at) "
                "VALUES (1, 'pump', 'offline', NULL)"
            )
        )

    with clean.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.upgrade()
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO devices (id, device_id, status) "
                    "VALUES (2, 'bad', 'online')"
                )
            )
            connection.commit()
        connection.rollback()

        connection.execute(
            text(
                "INSERT INTO alerts "
                "(id, device_id, alert_type, is_resolved) "
                "VALUES (1, 1, 'device_offline', 0)"
            )
        )
        connection.commit()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO alerts "
                    "(id, device_id, alert_type, is_resolved) "
                    "VALUES (2, 1, 'device_offline', 0)"
                )
            )
            connection.commit()
        connection.rollback()

        with Operations.context(context):
            module.downgrade()
        connection.commit()
        connection.execute(
            text(
                "INSERT INTO devices (id, device_id, status) "
                "VALUES (3, 'legacy', 'online')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO alerts "
                "(id, device_id, alert_type, is_resolved) "
                "VALUES (3, 1, 'device_offline', 0)"
            )
        )
        connection.commit()

    engine.dispose()
    clean.dispose()
