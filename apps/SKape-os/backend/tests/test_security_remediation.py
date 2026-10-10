import time
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from sqlalchemy import text

from app.crud.activity import log_activity as write_activity
from app.crud.alert import resolve_alert
from app.crud.device import heartbeat_device
from app.crud.invitation import (
    create_invitation,
    create_user_from_invitation,
    resend_invitation,
    revoke_invitation,
)
from app.crud.telemetry import create_telemetry
from app.models.activity import Activity
from app.models.alert import Alert
from app.models.device import Device
from app.models.invitation import Invitation
from app.models.organization import Organization
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.invitation import InvitationCreate
from app.schemas.telemetry import TelemetryCreate
from app.security import (
    LOGIN_FAILURE_DELAY_SECONDS,
    SECRET_KEY,
    hash_password,
)


PASSWORD = "Correct-horse-1"
CONFLICT = "Registration could not be completed."
DEVICE_CONFLICT = "Device could not be created."


def _user(db, org, role, email):
    user = User(
        name=role,
        email=email,
        hashed_password=hash_password(PASSWORD),
        role=role,
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def world(db):
    org = Organization(
        name="Org A",
        slug="org-a",
        is_active=True,
    )
    other = Organization(
        name="Org B",
        slug="org-b",
        is_active=True,
    )
    db.add_all([org, other])
    db.flush()
    owner = _user(db, org, "owner", "owner@example.com")
    admin = _user(db, org, "admin", "admin@example.com")
    manager = _user(db, org, "manager", "manager@example.com")
    employee = _user(db, org, "employee", "employee@example.com")
    other_owner = _user(
        db,
        other,
        "owner",
        "other-owner@example.com",
    )
    project = Project(
        name="Operations",
        organization_id=org.id,
        status="active",
    )
    db.add(project)
    db.flush()
    task = Task(
        title="Inspect pump",
        project_id=project.id,
        organization_id=org.id,
        status="todo",
        priority="medium",
    )
    db.add(task)
    db.commit()
    return {
        "org": org.id,
        "other_org": other.id,
        "owner": owner.email,
        "owner_id": owner.id,
        "admin": admin.email,
        "admin_id": admin.id,
        "manager": manager.email,
        "manager_id": manager.id,
        "employee": employee.email,
        "employee_id": employee.id,
        "other_owner": other_owner.email,
        "task": task.id,
    }


def _auth(api, email):
    response = api.post(
        "/api/v1/users/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {
        "Authorization": (
            f"Bearer {response.json()['access_token']}"
        )
    }


def _register(api, email, organization, password=PASSWORD):
    return api.post(
        "/api/v1/users/",
        json={
            "name": "New User",
            "email": email,
            "password": password,
            "organization_name": organization,
        },
    )


def _fail_after_audit(**kwargs):
    write_activity(**kwargs)
    raise RuntimeError("audit failed")


def test_registration_enforces_password_length_and_hides_conflicts(
    api,
    db,
):
    short = _register(
        api,
        "short@example.com",
        "Short Org",
        password="short",
    )
    assert short.status_code == 400
    assert (
        short.json()["detail"]
        == "Password must contain at least 8 characters."
    )
    assert db.query(User).count() == 0

    first = _register(
        api,
        "owner@example.com",
        "Org A",
    )
    assert first.status_code == 200

    duplicate_email = _register(
        api,
        "owner@example.com",
        "Different Org",
    )
    duplicate_org = _register(
        api,
        "second@example.com",
        "Org A",
    )
    assert duplicate_email.status_code == 400
    assert duplicate_org.status_code == 400
    assert duplicate_email.json()["detail"] == CONFLICT
    assert duplicate_org.json()["detail"] == CONFLICT
    assert "email" not in duplicate_email.json()["detail"].lower()
    assert "organization" not in duplicate_org.json()["detail"].lower()
    assert db.query(Organization).count() == 1


def test_failed_login_pays_a_minimum_delay(api):
    started = time.monotonic()
    missing = api.post(
        "/api/v1/users/login",
        data={
            "username": "missing@example.com",
            "password": "wrong-password",
        },
    )
    elapsed = time.monotonic() - started

    assert missing.status_code == 401
    assert elapsed >= LOGIN_FAILURE_DELAY_SECONDS


def test_only_the_owner_can_grant_admin(api, world):
    admin_headers = _auth(api, world["admin"])
    owner_headers = _auth(api, world["owner"])

    role_denied = api.patch(
        f"/api/v1/users/{world['employee_id']}/role",
        headers=admin_headers,
        json={"role": "admin"},
    )
    assert role_denied.status_code == 403

    invite_denied = api.post(
        "/api/v1/invitations/",
        headers=admin_headers,
        json={
            "email": "owner@example.com",
            "role": "admin",
        },
    )
    assert invite_denied.status_code == 403
    assert "permission" in invite_denied.json()["detail"]

    granted = api.patch(
        f"/api/v1/users/{world['manager_id']}/role",
        headers=owner_headers,
        json={"role": "admin"},
    )
    assert granted.status_code == 200
    assert granted.json()["role"] == "admin"

    invited = api.post(
        "/api/v1/invitations/",
        headers=owner_headers,
        json={
            "email": "new-admin@example.com",
            "role": "admin",
        },
    )
    assert invited.status_code == 200
    assert invited.json()["role"] == "admin"


def test_owner_cannot_create_a_second_organization(api, world, db):
    headers = _auth(api, world["owner"])
    before = db.query(Organization).count()

    created = api.post(
        "/api/v1/organizations/",
        headers=headers,
        json={"name": "Shadow Org"},
    )

    db.expire_all()
    assert created.status_code == 403
    assert db.query(Organization).count() == before
    assert (
        db.query(Organization)
        .filter(Organization.name == "Shadow Org")
        .count()
        == 0
    )


def test_duplicate_device_id_is_a_generic_conflict(api, world):
    owner = _auth(api, world["owner"])
    other = _auth(api, world["other_owner"])
    payload = {
        "device_id": "shared-pump",
        "name": "Pump",
        "device_type": "sensor",
    }

    first = api.post(
        "/api/v1/devices/",
        headers=owner,
        json=payload,
    )
    assert first.status_code == 200

    second = api.post(
        "/api/v1/devices/",
        headers=other,
        json=payload,
    )
    assert second.status_code == 400
    assert second.json()["detail"] == DEVICE_CONFLICT
    assert "Org A" not in second.text
    assert "already exists" not in second.text.lower()


def test_manager_cannot_forge_device_contact_state(api, world):
    headers = _auth(api, world["manager"])
    created = api.post(
        "/api/v1/devices/",
        headers=headers,
        json={
            "device_id": "forge-01",
            "name": "Forge",
            "device_type": "sensor",
        },
    )
    assert created.status_code == 200
    device_pk = created.json()["id"]

    forged = api.put(
        f"/api/v1/devices/{device_pk}",
        headers=headers,
        json={
            "name": "Renamed",
            "status": "online",
            "last_seen_at": "2026-01-01T00:00:00Z",
        },
    )
    assert forged.status_code == 200
    assert forged.json()["name"] == "Renamed"
    assert forged.json()["status"] == "offline"
    assert forged.json()["last_seen_at"] is None


def _provision(api, headers, device_pk):
    provisioned = api.post(
        f"/api/v1/devices/{device_pk}/credentials",
        headers=headers,
    )
    assert provisioned.status_code == 200
    return provisioned.json()["device_secret"]


def test_deactivated_device_stays_inactive_after_heartbeat_and_telemetry(
    api,
    world,
    db,
):
    headers = _auth(api, world["owner"])
    created = api.post(
        "/api/v1/devices/",
        headers=headers,
        json={
            "device_id": "pump-01",
            "name": "Pump",
            "device_type": "sensor",
        },
    )
    device_pk = created.json()["id"]
    secret = _provision(api, headers, device_pk)
    device_headers = {
        "X-Device-ID": "pump-01",
        "X-Device-Secret": secret,
    }

    heartbeat = api.post(
        "/api/v1/devices/heartbeat",
        headers=device_headers,
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["is_active"] is True
    assert heartbeat.json()["status"] == "online"
    seen = heartbeat.json()["last_seen_at"]

    deactivated = api.put(
        f"/api/v1/devices/{device_pk}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200

    rejected = api.post(
        "/api/v1/devices/heartbeat",
        headers=device_headers,
    )
    telemetry = api.post(
        f"/api/v1/devices/{device_pk}/telemetry",
        headers=device_headers,
        json={"temperature": 21.5},
    )
    assert rejected.status_code == 403
    assert telemetry.status_code == 403

    db.expire_all()
    stored = db.get(Device, device_pk)
    assert stored.is_active is False
    assert stored.last_seen_at.isoformat().startswith(
        seen.replace("Z", "+00:00")[:19]
    )


def test_heartbeat_and_telemetry_recheck_the_locked_row(
    db,
    session_factory,
    world,
):
    db.expire_on_commit = False
    device = Device(
        device_id="locked-01",
        name="Locked",
        device_type="sensor",
        status="offline",
        organization_id=world["org"],
        is_active=True,
    )
    db.add(device)
    db.commit()
    assert device.is_active is True

    other = session_factory()
    other.execute(
        text(
            "UPDATE devices SET is_active = false WHERE id = :id"
        ),
        {"id": device.id},
    )
    other.commit()
    other.close()
    assert device.is_active is True

    with pytest.raises(ValueError, match="inactive"):
        heartbeat_device(db, device.device_id)

    db.refresh(device)
    assert device.is_active is False
    assert device.status == "offline"

    with pytest.raises(ValueError, match="inactive"):
        create_telemetry(
            db,
            device,
            TelemetryCreate(temperature=20),
        )
    db.refresh(device)
    assert device.is_active is False
    assert device.status == "offline"


def test_alert_resolution_is_atomic_with_its_audit(
    api,
    db,
    world,
    monkeypatch,
):
    device = Device(
        device_id="alert-01",
        name="Alert",
        device_type="sensor",
        status="offline",
        organization_id=world["org"],
        is_active=True,
    )
    db.add(device)
    db.flush()
    alert = Alert(
        device_id=device.id,
        organization_id=world["org"],
        severity="warning",
        alert_type="device_offline",
        title="Offline",
        message="Device stopped reporting",
        is_resolved=False,
    )
    db.add(alert)
    db.commit()
    alert_id = alert.id

    headers = _auth(api, world["manager"])
    resolved = api.patch(
        f"/api/v1/alerts/{alert_id}/resolve",
        headers=headers,
    )
    assert resolved.status_code == 200
    db.expire_all()
    activity = (
        db.query(Activity)
        .filter(
            Activity.entity == "alert",
            Activity.entity_id == alert_id,
        )
        .one()
    )
    assert activity.action == "resolved"
    assert activity.user_id == world["manager_id"]

    second = Alert(
        device_id=device.id,
        organization_id=world["org"],
        severity="warning",
        alert_type="threshold",
        title="Hot",
        message="Temperature",
        is_resolved=False,
    )
    db.add(second)
    db.commit()
    second_id = second.id
    monkeypatch.setattr(
        "app.crud.alert.log_activity",
        _fail_after_audit,
    )
    failed = api.patch(
        f"/api/v1/alerts/{second_id}/resolve",
        headers=headers,
    )
    assert failed.status_code == 500
    assert failed.json()["detail"] == "Internal server error"
    db.expire_all()
    stored = db.get(Alert, second_id)
    assert stored.is_resolved is False
    assert (
        db.query(Activity)
        .filter(
            Activity.entity == "alert",
            Activity.entity_id == second_id,
        )
        .count()
        == 0
    )


def test_invitation_lifecycle_is_atomic_with_its_audit(
    db,
    world,
    monkeypatch,
):
    created = create_invitation(
        db,
        InvitationCreate(
            email="invitee@example.com",
            role="employee",
        ),
        world["org"],
        world["owner_id"],
    )
    created_id = created.id
    created_activity = (
        db.query(Activity)
        .filter(
            Activity.entity == "invitation",
            Activity.entity_id == created_id,
            Activity.action == "created",
        )
        .one()
    )
    assert created_activity.user_id == world["owner_id"]

    monkeypatch.setattr(
        "app.crud.invitation.log_activity",
        _fail_after_audit,
    )
    with pytest.raises(RuntimeError, match="audit failed"):
        revoke_invitation(
            db,
            created,
            world["admin_id"],
        )
    db.expire_all()
    stored = db.get(Invitation, created_id)
    assert stored.status == "pending"

    monkeypatch.undo()
    revoke_invitation(db, stored, world["admin_id"])
    assert stored.status == "revoked"
    revoked_activity = (
        db.query(Activity)
        .filter(
            Activity.entity == "invitation",
            Activity.entity_id == created_id,
            Activity.action == "revoked",
        )
        .one()
    )
    assert revoked_activity.user_id == world["admin_id"]

    monkeypatch.setattr(
        "app.crud.invitation.log_activity",
        _fail_after_audit,
    )
    with pytest.raises(RuntimeError, match="audit failed"):
        resend_invitation(db, stored, world["owner_id"])
    db.expire_all()
    stored = db.get(Invitation, created_id)
    assert stored.status == "revoked"

    monkeypatch.undo()
    resent = resend_invitation(db, stored, world["owner_id"])
    assert resent.status == "pending"
    resent_token = resent.token

    monkeypatch.setattr(
        "app.crud.invitation.log_activity",
        _fail_after_audit,
    )
    with pytest.raises(RuntimeError, match="audit failed"):
        create_user_from_invitation(
            db,
            resent,
            "Invitee",
            PASSWORD,
        )
    db.expire_all()
    stored = db.get(Invitation, created_id)
    assert stored.status == "pending"
    assert stored.token == resent_token
    assert (
        db.query(User)
        .filter(User.email == "invitee@example.com")
        .count()
        == 0
    )

    monkeypatch.undo()
    user = create_user_from_invitation(
        db,
        stored,
        "Invitee",
        PASSWORD,
    )
    accepted = (
        db.query(Activity)
        .filter(
            Activity.entity == "invitation",
            Activity.entity_id == created_id,
            Activity.action == "accepted",
        )
        .one()
    )
    assert accepted.user_id == user.id


def test_invitation_acceptance_uses_the_registration_password_rule(
    api,
    db,
    world,
):
    created = create_invitation(
        db,
        InvitationCreate(
            email="short-invite@example.com",
            role="employee",
        ),
        world["org"],
        world["owner_id"],
    )
    rejected = api.post(
        "/api/v1/invitations/accept",
        json={
            "token": created.token,
            "name": "Invitee",
            "password": "short",
        },
    )
    assert rejected.status_code == 400
    assert (
        rejected.json()["detail"]
        == "Password must contain at least 8 characters."
    )
    db.expire_all()
    assert db.get(Invitation, created.id).status == "pending"


def test_employees_cannot_read_the_activity_feed(api, world):
    employee = _auth(api, world["employee"])
    manager = _auth(api, world["manager"])

    denied = api.get(
        "/api/v1/activities/",
        headers=employee,
    )
    allowed = api.get(
        "/api/v1/activities/",
        headers=manager,
    )
    assert denied.status_code == 403
    assert allowed.status_code == 200


def test_comment_delete_matches_the_edit_rule(api, world):
    employee = _auth(api, world["employee"])
    manager = _auth(api, world["manager"])
    owner = _auth(api, world["owner"])

    created = api.post(
        "/api/v1/comments/",
        headers=employee,
        json={
            "content": "employee note",
            "task_id": world["task"],
        },
    )
    assert created.status_code == 200
    comment_id = created.json()["id"]

    denied = api.delete(
        f"/api/v1/comments/{comment_id}",
        headers=manager,
    )
    assert denied.status_code == 403
    assert "only delete your own" in denied.json()["detail"]

    removed = api.delete(
        f"/api/v1/comments/{comment_id}",
        headers=owner,
    )
    assert removed.status_code == 200

    own = api.post(
        "/api/v1/comments/",
        headers=employee,
        json={
            "content": "second note",
            "task_id": world["task"],
        },
    )
    deleted = api.delete(
        f"/api/v1/comments/{own.json()['id']}",
        headers=employee,
    )
    assert deleted.status_code == 200


def test_list_pagination_is_bounded(api, world):
    headers = _auth(api, world["owner"])
    for path in (
        "/api/v1/devices/",
        "/api/v1/projects/",
        "/api/v1/assets/",
    ):
        too_large = api.get(
            path,
            headers=headers,
            params={"limit": 101},
        )
        negative = api.get(
            path,
            headers=headers,
            params={"skip": -1},
        )
        assert too_large.status_code == 422
        assert negative.status_code == 422


def test_jwt_verification_rejects_bad_tokens_and_ignores_role_claims(
    api,
    world,
):
    expired = jwt.encode(
        {
            "sub": world["employee"],
            "role": "employee",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm="HS256",
    )
    wrong_algorithm = jwt.encode(
        {
            "sub": world["employee"],
            "role": "employee",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm="HS512",
    )
    forged_role = jwt.encode(
        {
            "sub": world["employee"],
            "role": "owner",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm="HS256",
    )

    expired_response = api.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    algorithm_response = api.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {wrong_algorithm}"},
    )
    forged = api.post(
        "/api/v1/organizations/current/deactivate",
        headers={"Authorization": f"Bearer {forged_role}"},
    )
    assert expired_response.status_code == 401
    assert algorithm_response.status_code == 401
    assert forged.status_code == 403


def test_resolve_alert_helper_records_the_actor(db, world):
    device = Device(
        device_id="helper-01",
        name="Helper",
        device_type="sensor",
        status="offline",
        organization_id=world["org"],
        is_active=True,
    )
    db.add(device)
    db.flush()
    alert = Alert(
        device_id=device.id,
        organization_id=world["org"],
        severity="info",
        alert_type="threshold",
        title="Info",
        message="Info",
        is_resolved=False,
    )
    db.add(alert)
    db.commit()

    resolve_alert(db, alert, world["owner_id"])
    activity = (
        db.query(Activity)
        .filter(Activity.entity_id == alert.id)
        .one()
    )
    assert activity.user_id == world["owner_id"]
