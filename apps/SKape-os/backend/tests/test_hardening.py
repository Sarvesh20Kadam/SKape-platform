import pytest

from app.crud.activity import log_activity as write_activity
from app.crud.asset import create_asset, delete_asset, update_asset
from app.crud.device import (
    create_device,
    delete_device,
    update_device,
)
from app.crud.project import (
    create_project,
    delete_project,
    update_project,
)
from app.models.activity import Activity
from app.models.asset import Asset
from app.models.device import Device
from app.models.organization import Organization
from app.models.project import Project
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetUpdate
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.security import hash_password


PASSWORD = "Correct-horse-1"


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
        "owner": owner.email,
        "owner_id": owner.id,
    }


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


def _fail_after_audit(**kwargs):
    write_activity(**kwargs)
    raise RuntimeError("audit failed")


def _actions(session, entity, entity_id):
    return [
        item.action
        for item in session.query(Activity)
        .filter(
            Activity.entity == entity,
            Activity.entity_id == entity_id,
        )
        .order_by(Activity.id)
        .all()
    ]


def test_invalid_task_list_filters_are_rejected(api, world):
    headers = _auth(api, world["owner"])

    invalid_status = api.get(
        "/api/v1/tasks/",
        params={"status": "not-a-status"},
        headers=headers,
    )
    assert invalid_status.status_code == 400
    assert invalid_status.json()["detail"] == "Invalid task status."

    invalid_priority = api.get(
        "/api/v1/tasks/",
        params={"priority": "not-a-priority"},
        headers=headers,
    )
    assert invalid_priority.status_code == 400
    assert invalid_priority.json()["detail"] == "Invalid task priority."

    invalid_limit = api.get(
        "/api/v1/tasks/",
        params={"limit": 101},
        headers=headers,
    )
    assert invalid_limit.status_code == 422


def test_project_create_rolls_back_when_audit_fails(
    db,
    world,
    session_factory,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.crud.project.log_activity",
        _fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        create_project(
            db=db,
            project=ProjectCreate(
                name="Must roll back",
                description="Audit failure test",
            ),
            organization_id=world["org_a"],
            user_id=world["owner_id"],
        )

    check = session_factory()
    try:
        assert (
            check.query(Project)
            .filter(Project.name == "Must roll back")
            .count()
            == 0
        )
        assert (
            check.query(Activity)
            .filter(Activity.entity == "project")
            .count()
            == 0
        )
    finally:
        check.close()


def test_project_update_rolls_back_when_audit_fails(
    db,
    world,
    session_factory,
    monkeypatch,
):
    created = create_project(
        db=db,
        project=ProjectCreate(
            name="Stable project",
            description="Keep this description",
        ),
        organization_id=world["org_a"],
        user_id=world["owner_id"],
    )

    monkeypatch.setattr(
        "app.crud.project.log_activity",
        _fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        update_project(
            db=db,
            project_id=created.id,
            organization_id=world["org_a"],
            user_id=world["owner_id"],
            updated_project=ProjectUpdate(
                name="Changed project",
                description="Changed description",
                status="archived",
            ),
        )

    check = session_factory()
    try:
        stored = check.get(Project, created.id)
        assert stored.name == "Stable project"
        assert stored.description == "Keep this description"
        assert stored.status == "active"
        assert _actions(check, "project", created.id) == ["created"]
    finally:
        check.close()


def test_project_delete_rolls_back_when_audit_fails(
    db,
    world,
    session_factory,
    monkeypatch,
):
    created = create_project(
        db=db,
        project=ProjectCreate(
            name="Keep project",
            description="Still here",
        ),
        organization_id=world["org_a"],
        user_id=world["owner_id"],
    )

    monkeypatch.setattr(
        "app.crud.project.log_activity",
        _fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        delete_project(
            db=db,
            project_id=created.id,
            organization_id=world["org_a"],
            user_id=world["owner_id"],
        )

    check = session_factory()
    try:
        stored = check.get(Project, created.id)
        assert stored is not None
        assert stored.name == "Keep project"
        assert stored.description == "Still here"
        assert stored.status == "active"
        assert _actions(check, "project", created.id) == ["created"]
    finally:
        check.close()


def test_project_delete_returns_snapshot(
    api,
    world,
    session_factory,
):
    headers = _auth(api, world["owner"])
    created = api.post(
        "/api/v1/projects/",
        headers=headers,
        json={
            "name": "Delete me",
            "description": "Project snapshot",
        },
    )
    assert created.status_code == 200, created.text
    project_id = created.json()["id"]

    deleted = api.delete(
        f"/api/v1/projects/{project_id}",
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["id"] == project_id
    assert body["name"] == "Delete me"
    assert body["description"] == "Project snapshot"
    assert body["status"] == "active"

    check = session_factory()
    try:
        assert check.get(Project, project_id) is None
        assert _actions(check, "project", project_id) == [
            "created",
            "deleted",
        ]
    finally:
        check.close()


def test_asset_create_rolls_back_when_audit_fails(
    db,
    world,
    session_factory,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.crud.asset.log_activity",
        _fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        create_asset(
            db=db,
            asset=AssetCreate(
                name="Rollback asset",
                asset_type="sensor",
            ),
            organization_id=world["org_a"],
            user_id=world["owner_id"],
        )

    check = session_factory()
    try:
        assert (
            check.query(Asset)
            .filter(Asset.name == "Rollback asset")
            .count()
            == 0
        )
        assert (
            check.query(Activity)
            .filter(Activity.entity == "asset")
            .count()
            == 0
        )
    finally:
        check.close()


def test_asset_update_rolls_back_when_audit_fails(
    db,
    world,
    session_factory,
    monkeypatch,
):
    created = create_asset(
        db=db,
        asset=AssetCreate(
            name="Stable asset",
            asset_type="sensor",
            description="Original",
            location="Plant",
        ),
        organization_id=world["org_a"],
        user_id=world["owner_id"],
    )

    monkeypatch.setattr(
        "app.crud.asset.log_activity",
        _fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        update_asset(
            db=db,
            asset_id=created.id,
            organization_id=world["org_a"],
            user_id=world["owner_id"],
            updated_asset=AssetUpdate(
                name="Changed asset",
                location="Warehouse",
            ),
        )

    check = session_factory()
    try:
        stored = check.get(Asset, created.id)
        assert stored.name == "Stable asset"
        assert stored.asset_type == "sensor"
        assert stored.description == "Original"
        assert stored.location == "Plant"
        assert stored.status == "active"
        assert stored.is_active is True
        assert _actions(check, "asset", created.id) == ["created"]
    finally:
        check.close()


def test_asset_delete_rolls_back_when_audit_fails(
    db,
    world,
    session_factory,
    monkeypatch,
):
    created = create_asset(
        db=db,
        asset=AssetCreate(
            name="Keep asset",
            asset_type="sensor",
        ),
        organization_id=world["org_a"],
        user_id=world["owner_id"],
    )

    monkeypatch.setattr(
        "app.crud.asset.log_activity",
        _fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        delete_asset(
            db=db,
            asset_id=created.id,
            organization_id=world["org_a"],
            user_id=world["owner_id"],
        )

    check = session_factory()
    try:
        stored = check.get(Asset, created.id)
        assert stored is not None
        assert stored.name == "Keep asset"
        assert stored.asset_type == "sensor"
        assert stored.is_active is True
        assert _actions(check, "asset", created.id) == ["created"]
    finally:
        check.close()


def test_asset_delete_returns_snapshot(
    api,
    world,
    session_factory,
):
    headers = _auth(api, world["owner"])
    created = api.post(
        "/api/v1/assets/",
        headers=headers,
        json={
            "name": "Delete asset",
            "asset_type": "sensor",
            "description": "Asset snapshot",
        },
    )
    assert created.status_code == 200, created.text
    asset_id = created.json()["id"]

    deleted = api.delete(
        f"/api/v1/assets/{asset_id}",
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["id"] == asset_id
    assert body["name"] == "Delete asset"
    assert body["asset_type"] == "sensor"
    assert body["description"] == "Asset snapshot"
    assert body["status"] == "active"
    assert body["is_active"] is True
    assert body["organization_id"] == world["org_a"]

    check = session_factory()
    try:
        assert check.get(Asset, asset_id) is None
        assert _actions(check, "asset", asset_id) == [
            "created",
            "deleted",
        ]
    finally:
        check.close()


def test_device_create_rolls_back_when_audit_fails(
    db,
    world,
    session_factory,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.crud.device.log_activity",
        _fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        create_device(
            db=db,
            device=DeviceCreate(
                device_id="rollback-device",
                name="Rollback device",
                device_type="sensor",
            ),
            organization_id=world["org_a"],
            user_id=world["owner_id"],
        )

    check = session_factory()
    try:
        assert (
            check.query(Device)
            .filter(Device.device_id == "rollback-device")
            .count()
            == 0
        )
        assert (
            check.query(Activity)
            .filter(Activity.entity == "device")
            .count()
            == 0
        )
    finally:
        check.close()


def test_device_update_rolls_back_when_audit_fails(
    db,
    world,
    session_factory,
    monkeypatch,
):
    created = create_device(
        db=db,
        device=DeviceCreate(
            device_id="stable-device",
            name="Stable device",
            device_type="sensor",
        ),
        organization_id=world["org_a"],
        user_id=world["owner_id"],
    )

    monkeypatch.setattr(
        "app.crud.device.log_activity",
        _fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        update_device(
            db=db,
            device_id=created.id,
            organization_id=world["org_a"],
            user_id=world["owner_id"],
            updated_device=DeviceUpdate(
                name="Changed device",
                device_type="gateway",
            ),
        )

    check = session_factory()
    try:
        stored = check.get(Device, created.id)
        assert stored.device_id == "stable-device"
        assert stored.name == "Stable device"
        assert stored.device_type == "sensor"
        assert stored.status == "offline"
        assert stored.is_active is True
        assert _actions(check, "device", created.id) == ["created"]
    finally:
        check.close()


def test_device_delete_rolls_back_when_audit_fails(
    db,
    world,
    session_factory,
    monkeypatch,
):
    created = create_device(
        db=db,
        device=DeviceCreate(
            device_id="keep-device",
            name="Keep device",
            device_type="sensor",
        ),
        organization_id=world["org_a"],
        user_id=world["owner_id"],
    )

    monkeypatch.setattr(
        "app.crud.device.log_activity",
        _fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        delete_device(
            db=db,
            device_id=created.id,
            organization_id=world["org_a"],
            user_id=world["owner_id"],
        )

    check = session_factory()
    try:
        stored = check.get(Device, created.id)
        assert stored is not None
        assert stored.device_id == "keep-device"
        assert stored.name == "Keep device"
        assert stored.device_type == "sensor"
        assert stored.is_active is True
        assert _actions(check, "device", created.id) == ["created"]
    finally:
        check.close()


def test_device_delete_returns_snapshot(
    api,
    world,
    session_factory,
):
    headers = _auth(api, world["owner"])
    created = api.post(
        "/api/v1/devices/",
        headers=headers,
        json={
            "device_id": "delete-device",
            "name": "Delete device",
            "device_type": "sensor",
        },
    )
    assert created.status_code == 200, created.text
    device_pk = created.json()["id"]

    deleted = api.delete(
        f"/api/v1/devices/{device_pk}",
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["id"] == device_pk
    assert body["device_id"] == "delete-device"
    assert body["name"] == "Delete device"
    assert body["device_type"] == "sensor"
    assert body["status"] == "offline"
    assert body["is_active"] is True
    assert body["organization_id"] == world["org_a"]

    check = session_factory()
    try:
        assert check.get(Device, device_pk) is None
        assert _actions(check, "device", device_pk) == [
            "created",
            "deleted",
        ]
    finally:
        check.close()
