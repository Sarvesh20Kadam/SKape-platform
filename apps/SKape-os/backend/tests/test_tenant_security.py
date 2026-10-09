import importlib.util
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401
from app.crud.activity import log_activity as write_activity
from app.crud.organization import (
    activate_organization,
    deactivate_organization,
)
from app.models.activity import Activity
from app.models.comment import Comment
from app.models.device_credential import DeviceCredential
from app.models.invitation import Invitation
from app.models.organization import Organization
from app.models.project import Project
from app.models.user import User
from app.security import hash_password


PASSWORD = "Correct-horse-1"
UNAVAILABLE_EMAIL = "This email cannot be invited."
MEMBERSHIP_LOCKED = (
    "You already belong to an organization. "
    "Invitations cannot change organization membership."
)


def _migration_module(filename, module_name):
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / filename
    )
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _organization_active_migration():
    return _migration_module(
        "c4e8a1b92f30_set_organization_active_server_default.py",
        "organization_active_server_default",
    )


def _email_uniqueness_migration():
    return _migration_module(
        "e3a91c7b2d44_enforce_case_insensitive_email_uniqueness.py",
        "case_insensitive_email_uniqueness",
    )


def _org(db, name, slug, active=True):
    org = Organization(
        name=name,
        slug=slug,
        is_active=active,
    )
    db.add(org)
    db.flush()
    return org


def _user(db, org, role, email, active=True):
    user = User(
        name=role,
        email=email,
        hashed_password=hash_password(PASSWORD),
        role=role,
        is_active=active,
        organization_id=org.id,
    )
    db.add(user)
    db.flush()
    return user


def _project(db, org):
    project = Project(
        name="Operations",
        organization_id=org.id,
        status="active",
    )
    db.add(project)
    db.flush()
    return project


@pytest.fixture
def world(db):
    org_a = _org(db, "Org A", "org-a")
    org_b = _org(db, "Org B", "org-b")
    owner = _user(db, org_a, "owner", "owner@example.com")
    admin = _user(db, org_a, "admin", "admin@example.com")
    manager = _user(db, org_a, "manager", "manager@example.com")
    employee = _user(
        db,
        org_a,
        "employee",
        "employee@example.com",
    )
    other_owner = _user(
        db,
        org_b,
        "owner",
        "other-owner@example.com",
    )
    inactive_user = _user(
        db,
        org_a,
        "employee",
        "inactive@example.com",
        active=False,
    )
    project = _project(db, org_a)
    other_project = _project(db, org_b)
    db.commit()

    return {
        "org_a": org_a.id,
        "org_b": org_b.id,
        "project": project.id,
        "other_project": other_project.id,
        "owner": owner.email,
        "admin": admin.email,
        "manager": manager.email,
        "employee": employee.email,
        "other_owner": other_owner.email,
        "inactive_user": inactive_user.email,
        "owner_id": owner.id,
    }


def _login(api, email, password=PASSWORD):
    return api.post(
        "/api/v1/users/login",
        data={
            "username": email,
            "password": password,
        },
    )


def _auth(api, email):
    response = _login(api, email)
    assert response.status_code == 200, response.text
    return {
        "Authorization": (
            f"Bearer {response.json()['access_token']}"
        )
    }


def _detail(response):
    body = response.json()
    return body.get("detail", body.get("message", body))


def test_owner_can_deactivate_and_reactivate_only_their_org(
    api,
    world,
):
    headers = _auth(api, world["owner"])

    deactivated = api.post(
        "/api/v1/organizations/current/deactivate",
        headers=headers,
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    blocked = api.get(
        "/api/v1/organizations/current",
        headers=headers,
    )
    assert blocked.status_code == 403
    assert _detail(blocked) == "Organization is inactive"

    tasks = api.get(
        "/api/v1/tasks/",
        headers=headers,
    )
    assert tasks.status_code == 403
    assert _detail(tasks) == "Organization is inactive"

    login = _login(api, world["owner"])
    assert login.status_code == 403
    assert _detail(login) == "Organization is inactive"
    assert "access_token" not in login.json()

    restored = api.post(
        "/api/v1/organizations/current/activate",
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True

    current = api.get(
        "/api/v1/organizations/current",
        headers=headers,
    )
    assert current.status_code == 200
    assert current.json()["is_active"] is True

    api.post(
        "/api/v1/organizations/current/deactivate",
        headers=headers,
    )
    reactivated = api.patch(
        f"/api/v1/organizations/{world['org_a']}/reactivate",
        headers=headers,
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["id"] == world["org_a"]
    assert reactivated.json()["is_active"] is True


def test_recovery_is_owner_only_and_org_scoped(api, world):
    owner_headers = _auth(api, world["owner"])
    admin_headers = _auth(api, world["admin"])
    other_headers = _auth(api, world["other_owner"])

    api.post(
        "/api/v1/organizations/current/deactivate",
        headers=owner_headers,
    )

    admin_attempt = api.post(
        "/api/v1/organizations/current/activate",
        headers=admin_headers,
    )
    assert admin_attempt.status_code == 403
    assert "permission" in _detail(admin_attempt)

    foreign = api.patch(
        f"/api/v1/organizations/{world['org_a']}/reactivate",
        headers=other_headers,
    )
    assert foreign.status_code == 403
    assert "don't have access" in _detail(foreign)

    still_inactive = api.get(
        "/api/v1/tasks/",
        headers=owner_headers,
    )
    assert still_inactive.status_code == 403
    assert _detail(still_inactive) == "Organization is inactive"


def test_admin_cannot_change_is_active_through_update(
    api,
    world,
    session_factory,
):
    headers = _auth(api, world["admin"])

    updated = api.put(
        "/api/v1/organizations/current",
        headers=headers,
        json={
            "name": "Renamed Org",
            "is_active": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed Org"
    assert updated.json()["is_active"] is True

    session = session_factory()
    try:
        org = session.get(Organization, world["org_a"])
        assert org.name == "Renamed Org"
        assert org.is_active is True
    finally:
        session.close()


def _fail_after_organization_audit(**kwargs):
    write_activity(**kwargs)
    raise RuntimeError("audit failed")


def _organization_actions(session, organization_id):
    return [
        item.action
        for item in session.query(Activity)
        .filter(
            Activity.entity == "organization",
            Activity.entity_id == organization_id,
        )
        .all()
    ]


def test_deactivation_audit_failure_rolls_back(
    db,
    world,
    session_factory,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.crud.organization.log_activity",
        _fail_after_organization_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        deactivate_organization(
            db=db,
            organization_id=world["org_a"],
            user_id=world["owner_id"],
        )

    session = session_factory()
    try:
        org = session.get(Organization, world["org_a"])
        assert org.is_active is True
        assert "deactivated" not in _organization_actions(
            session,
            world["org_a"],
        )
    finally:
        session.close()


def test_activation_audit_failure_rolls_back(
    db,
    world,
    session_factory,
    monkeypatch,
):
    org = db.get(Organization, world["org_a"])
    org.is_active = False
    db.commit()

    monkeypatch.setattr(
        "app.crud.organization.log_activity",
        _fail_after_organization_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        activate_organization(
            db=db,
            organization_id=world["org_a"],
            user_id=world["owner_id"],
        )

    session = session_factory()
    try:
        stored = session.get(Organization, world["org_a"])
        assert stored.is_active is False
        assert "activated" not in _organization_actions(
            session,
            world["org_a"],
        )
    finally:
        session.close()


def test_login_rejects_inactive_users_and_organizations(
    api,
    world,
):
    inactive_user = _login(api, world["inactive_user"])
    assert inactive_user.status_code == 403
    assert _detail(inactive_user) == "User account is inactive"

    wrong_password = _login(
        api,
        world["owner"],
        password="not-the-password",
    )
    assert wrong_password.status_code == 401

    headers = _auth(api, world["owner"])
    api.post(
        "/api/v1/organizations/current/deactivate",
        headers=headers,
    )

    inactive_org = _login(api, world["admin"])
    assert inactive_org.status_code == 403
    assert _detail(inactive_org) == "Organization is inactive"


def test_invitation_tokens_are_not_listed_and_emails_are_generic(
    api,
    world,
    session_factory,
):
    owner_headers = _auth(api, world["owner"])
    manager_headers = _auth(api, world["manager"])
    other_headers = _auth(api, world["other_owner"])

    same_org = api.post(
        "/api/v1/invitations/",
        headers=owner_headers,
        json={
            "email": world["employee"],
            "role": "employee",
        },
    )
    other_org = api.post(
        "/api/v1/invitations/",
        headers=owner_headers,
        json={
            "email": world["other_owner"],
            "role": "manager",
        },
    )
    assert same_org.status_code == 409
    assert other_org.status_code == 409
    assert _detail(same_org) == UNAVAILABLE_EMAIL
    assert _detail(other_org) == UNAVAILABLE_EMAIL

    invalid_role = api.post(
        "/api/v1/invitations/",
        headers=owner_headers,
        json={
            "email": "new-admin@example.com",
            "role": "owner",
        },
    )
    assert invalid_role.status_code == 400

    created = api.post(
        "/api/v1/invitations/",
        headers=owner_headers,
        json={
            "email": "new.person@example.com",
            "role": "employee",
        },
    )
    assert created.status_code == 200
    token = created.json()["token"]
    invitation_id = created.json()["id"]
    assert token

    listed = api.get(
        "/api/v1/invitations/",
        headers=manager_headers,
    )
    assert listed.status_code == 200
    assert listed.json()
    assert all("token" not in item for item in listed.json())
    assert token not in listed.text

    resent = api.post(
        f"/api/v1/invitations/{invitation_id}/resend",
        headers=owner_headers,
    )
    assert resent.status_code == 200
    assert resent.json()["token"]
    assert resent.json()["token"] != token

    hidden = api.get(
        "/api/v1/invitations/",
        headers=other_headers,
    )
    assert hidden.status_code == 200
    assert hidden.json() == []

    revoke = api.delete(
        f"/api/v1/invitations/{invitation_id}",
        headers=other_headers,
    )
    assert revoke.status_code == 404

    resend_foreign = api.post(
        f"/api/v1/invitations/{invitation_id}/resend",
        headers=other_headers,
    )
    assert resend_foreign.status_code == 404

    accepted = api.post(
        "/api/v1/invitations/accept",
        json={
            "token": resent.json()["token"],
            "name": "New Person",
            "password": PASSWORD,
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["organization_id"] == world["org_a"]
    assert accepted.json()["role"] == "employee"

    joined = _login(api, "new.person@example.com")
    assert joined.status_code == 200


def test_existing_user_cannot_change_membership_by_invitation(
    api,
    world,
    session_factory,
):
    session = session_factory()
    try:
        invitation = Invitation(
            email=world["owner"],
            token="existing-user-token",
            role="admin",
            status="pending",
            organization_id=world["org_b"],
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=2),
        )
        session.add(invitation)
        session.commit()
        invitation_id = invitation.id
    finally:
        session.close()

    headers = _auth(api, world["owner"])
    response = api.post(
        "/api/v1/invitations/accept-existing",
        headers=headers,
        json={"token": "existing-user-token"},
    )
    assert response.status_code == 409
    assert _detail(response) == MEMBERSHIP_LOCKED

    session = session_factory()
    try:
        owner = session.get(User, world["owner_id"])
        stored = session.get(Invitation, invitation_id)
        assert owner.organization_id == world["org_a"]
        assert owner.role == "owner"
        assert stored.status == "pending"
    finally:
        session.close()

    mismatch = api.post(
        "/api/v1/invitations/accept-existing",
        headers=headers,
        json={"token": "missing-token"},
    )
    assert mismatch.status_code == 404


def test_task_access_stays_inside_the_organization_and_delete_serializes(
    api,
    world,
):
    owner_headers = _auth(api, world["owner"])
    other_headers = _auth(api, world["other_owner"])

    created = api.post(
        "/api/v1/tasks/",
        headers=owner_headers,
        json={
            "title": "Inspect valves",
            "project_id": world["project"],
            "priority": "high",
        },
    )
    assert created.status_code == 200
    task_id = created.json()["id"]

    foreign_project = api.post(
        "/api/v1/tasks/",
        headers=owner_headers,
        json={
            "title": "Wrong project",
            "project_id": world["other_project"],
            "priority": "low",
        },
    )
    assert foreign_project.status_code == 400

    hidden = api.get(
        f"/api/v1/tasks/{task_id}",
        headers=other_headers,
    )
    assert hidden.status_code == 404

    foreign_update = api.put(
        f"/api/v1/tasks/{task_id}",
        headers=other_headers,
        json={"title": "Taken over"},
    )
    assert foreign_update.status_code == 404

    foreign_delete = api.delete(
        f"/api/v1/tasks/{task_id}",
        headers=other_headers,
    )
    assert foreign_delete.status_code == 404

    deleted = api.delete(
        f"/api/v1/tasks/{task_id}",
        headers=owner_headers,
    )
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["id"] == task_id
    assert body["title"] == "Inspect valves"
    assert body["organization_id"] == world["org_a"]
    assert body["project_id"] == world["project"]

    missing = api.get(
        f"/api/v1/tasks/{task_id}",
        headers=owner_headers,
    )
    assert missing.status_code == 404


def test_invitation_and_login_emails_are_case_insensitive(
    api,
    world,
):
    headers = _auth(api, world["owner"])

    same_org = api.post(
        "/api/v1/invitations/",
        headers=headers,
        json={
            "email": "Employee@Example.com",
            "role": "manager",
        },
    )
    other_org = api.post(
        "/api/v1/invitations/",
        headers=headers,
        json={
            "email": "Other-Owner@Example.com",
            "role": "employee",
        },
    )
    assert same_org.status_code == 409
    assert other_org.status_code == 409
    assert _detail(same_org) == UNAVAILABLE_EMAIL
    assert _detail(other_org) == UNAVAILABLE_EMAIL

    registered = api.post(
        "/api/v1/users/",
        json={
            "name": "Case Owner",
            "email": "Case.Owner@Example.com",
            "password": PASSWORD,
            "organization_name": "Case Org",
        },
    )
    assert registered.status_code == 200
    assert registered.json()["email"] == "case.owner@example.com"

    login = _login(api, "Owner@Example.com")
    assert login.status_code == 200

    inactive = _login(api, "INACTIVE@example.com")
    assert inactive.status_code == 403
    assert _detail(inactive) == "User account is inactive"

    wrong_password = _login(
        api,
        "Owner@Example.com",
        password="not-the-password",
    )
    assert wrong_password.status_code == 401


def test_inactive_organization_cannot_accept_invitation(
    api,
    world,
    session_factory,
):
    headers = _auth(api, world["owner"])
    created = api.post(
        "/api/v1/invitations/",
        headers=headers,
        json={
            "email": "later.person@example.com",
            "role": "employee",
        },
    )
    assert created.status_code == 200
    token = created.json()["token"]

    deactivated = api.post(
        "/api/v1/organizations/current/deactivate",
        headers=headers,
    )
    assert deactivated.status_code == 200

    rejected = api.post(
        "/api/v1/invitations/accept",
        json={
            "token": token,
            "name": "Later Person",
            "password": PASSWORD,
        },
    )
    assert rejected.status_code == 403
    assert _detail(rejected) == "Organization is inactive"

    session = session_factory()
    try:
        invitation = (
            session.query(Invitation)
            .filter(Invitation.token == token)
            .one()
        )
        user = (
            session.query(User)
            .filter(User.email == "later.person@example.com")
            .first()
        )
        assert invitation.status == "pending"
        assert user is None
    finally:
        session.close()

    restored = api.post(
        "/api/v1/organizations/current/activate",
        headers=headers,
    )
    assert restored.status_code == 200

    accepted = api.post(
        "/api/v1/invitations/accept",
        json={
            "token": token,
            "name": "Later Person",
            "password": PASSWORD,
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["organization_id"] == world["org_a"]
    assert accepted.json()["role"] == "employee"

    joined = _login(api, "later.person@example.com")
    assert joined.status_code == 200


def test_delete_task_removes_comments_and_still_serializes(
    api,
    world,
    session_factory,
):
    headers = _auth(api, world["owner"])
    created = api.post(
        "/api/v1/tasks/",
        headers=headers,
        json={
            "title": "Commented task",
            "project_id": world["project"],
            "priority": "medium",
        },
    )
    assert created.status_code == 200
    task_id = created.json()["id"]

    comment = api.post(
        "/api/v1/comments/",
        headers=headers,
        json={
            "content": "Check the seal",
            "task_id": task_id,
        },
    )
    assert comment.status_code == 200
    comment_id = comment.json()["id"]

    deleted = api.delete(
        f"/api/v1/tasks/{task_id}",
        headers=headers,
    )
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["id"] == task_id
    assert body["title"] == "Commented task"
    assert body["organization_id"] == world["org_a"]

    session = session_factory()
    try:
        remaining = (
            session.query(Comment)
            .filter(Comment.id == comment_id)
            .first()
        )
        assert remaining is None
    finally:
        session.close()


def test_organization_active_migration_backfills_nulls():
    module = _organization_active_migration()
    engine = create_engine("sqlite://")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE organizations (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    is_active BOOLEAN
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO organizations (id, name, is_active)
                VALUES
                    (1, 'Missing', NULL),
                    (2, 'Disabled', 0),
                    (3, 'Enabled', 1)
                """
            )
        )

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.upgrade()
        connection.commit()

    with engine.connect() as connection:
        rows = {
            row.id: row.is_active
            for row in connection.execute(
                text(
                    "SELECT id, is_active FROM organizations "
                    "ORDER BY id"
                )
            )
        }
        assert bool(rows[1]) is True
        assert bool(rows[2]) is False
        assert bool(rows[3]) is True

        connection.execute(
            text(
                "INSERT INTO organizations (id, name) "
                "VALUES (4, 'Defaulted')"
            )
        )
        connection.commit()
        defaulted = connection.execute(
            text(
                "SELECT is_active FROM organizations WHERE id = 4"
            )
        ).scalar()
        assert bool(defaulted) is True

        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.downgrade()
        connection.commit()

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name) "
                    "VALUES (5, 'No default')"
                )
            )
            connection.commit()

    engine.dispose()


def _device_headers(device_id, secret):
    return {
        "X-Device-ID": device_id,
        "X-Device-Secret": secret,
    }


def test_device_auth_blocks_inactive_organizations_and_revoked_credentials(
    api,
    world,
    session_factory,
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
    assert created.status_code == 200
    device_pk = created.json()["id"]
    device_key = created.json()["device_id"]

    provisioned = api.post(
        f"/api/v1/devices/{device_pk}/credentials",
        headers=headers,
    )
    assert provisioned.status_code == 200
    secret = provisioned.json()["device_secret"]
    assert secret

    telemetry = api.post(
        f"/api/v1/devices/{device_pk}/telemetry",
        headers=_device_headers(device_key, secret),
        json={"temperature": 21.5},
    )
    assert telemetry.status_code == 200
    assert telemetry.json()["temperature"] == 21.5

    wrong_secret = api.post(
        f"/api/v1/devices/{device_pk}/telemetry",
        headers=_device_headers(device_key, "not-the-secret"),
        json={"temperature": 22},
    )
    assert wrong_secret.status_code == 401
    assert _detail(wrong_secret) == "Invalid device credentials"

    health = api.get(
        f"/api/v1/devices/{device_pk}/health",
        headers=headers,
    )
    assert health.status_code == 200
    assert health.json()["sensors_total"] == 4

    platform = api.get("/api/v1/health/")
    assert platform.status_code == 200
    assert platform.json()["status"] == "healthy"

    devices = api.get(
        "/api/v1/devices/",
        headers=headers,
    )
    assert devices.status_code == 200
    assert any(item["id"] == device_pk for item in devices.json())

    session = session_factory()
    try:
        credential = (
            session.query(DeviceCredential)
            .filter(DeviceCredential.device_id == device_pk)
            .one()
        )
        used_at = credential.last_used_at
        assert used_at is not None
    finally:
        session.close()

    deactivated = api.post(
        "/api/v1/organizations/current/deactivate",
        headers=headers,
    )
    assert deactivated.status_code == 200

    blocked = api.post(
        f"/api/v1/devices/{device_pk}/telemetry",
        headers=_device_headers(device_key, secret),
        json={"temperature": 30},
    )
    assert blocked.status_code == 403
    assert _detail(blocked) == "Organization is inactive"

    heartbeat = api.post(
        "/api/v1/devices/heartbeat",
        headers=_device_headers(device_key, secret),
    )
    assert heartbeat.status_code == 403
    assert _detail(heartbeat) == "Organization is inactive"

    admin_health = api.get(
        f"/api/v1/devices/{device_pk}/health",
        headers=headers,
    )
    assert admin_health.status_code == 403
    assert _detail(admin_health) == "Organization is inactive"

    platform = api.get("/api/v1/health/")
    assert platform.status_code == 200
    assert platform.json()["status"] == "healthy"

    session = session_factory()
    try:
        credential = (
            session.query(DeviceCredential)
            .filter(DeviceCredential.device_id == device_pk)
            .one()
        )
        assert credential.last_used_at == used_at
    finally:
        session.close()

    restored = api.post(
        "/api/v1/organizations/current/activate",
        headers=headers,
    )
    assert restored.status_code == 200

    resumed = api.post(
        f"/api/v1/devices/{device_pk}/telemetry",
        headers=_device_headers(device_key, secret),
        json={"temperature": 19},
    )
    assert resumed.status_code == 200

    restored_health = api.get(
        f"/api/v1/devices/{device_pk}/health",
        headers=headers,
    )
    assert restored_health.status_code == 200

    revoked = api.post(
        f"/api/v1/devices/{device_pk}/credentials/revoke",
        headers=headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["is_active"] is False

    rejected = api.post(
        f"/api/v1/devices/{device_pk}/telemetry",
        headers=_device_headers(device_key, secret),
        json={"temperature": 18},
    )
    assert rejected.status_code == 401
    assert _detail(rejected) == "Invalid device credentials"

    revoked_heartbeat = api.post(
        "/api/v1/devices/heartbeat",
        headers=_device_headers(device_key, secret),
    )
    assert revoked_heartbeat.status_code == 401
    assert (
        _detail(revoked_heartbeat)
        == "Invalid device credentials"
    )


def test_case_variant_registration_is_rejected_by_the_database(
    api,
    session_factory,
):
    first = api.post(
        "/api/v1/users/",
        json={
            "name": "Case Owner",
            "email": "Case.Owner@Example.com",
            "password": PASSWORD,
            "organization_name": "Constraint Org",
        },
    )
    assert first.status_code == 200
    assert first.json()["email"] == "case.owner@example.com"

    second = api.post(
        "/api/v1/users/",
        json={
            "name": "Other Case",
            "email": "case.owner@example.com",
            "password": PASSWORD,
            "organization_name": "Constraint Org Two",
        },
    )
    assert second.status_code == 400
    assert _detail(second) == "Email already registered"

    session = session_factory()
    try:
        user = (
            session.query(User)
            .filter(User.email == "case.owner@example.com")
            .one()
        )
        session.add(
            User(
                name="Variant",
                email="CASE.OWNER@example.com",
                hashed_password=user.hashed_password,
                role="employee",
                is_active=True,
                organization_id=user.organization_id,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_email_uniqueness_migration_rejects_case_variants():
    module = _email_uniqueness_migration()
    engine = create_engine("sqlite://")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    email VARCHAR NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO users (id, email)
                VALUES
                    (1, 'Owner@Example.com'),
                    (2, 'owner@example.com')
                """
            )
        )

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with pytest.raises(RuntimeError, match="not merged"):
            with Operations.context(context):
                module.upgrade()

        rows = connection.execute(
            text("SELECT email FROM users ORDER BY id")
        ).fetchall()
        assert [row[0] for row in rows] == [
            "Owner@Example.com",
            "owner@example.com",
        ]

    clean = create_engine("sqlite://")
    with clean.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    email VARCHAR NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, email) "
                "VALUES (1, 'owner@example.com')"
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
                    "INSERT INTO users (id, email) "
                    "VALUES (2, 'Owner@Example.com')"
                )
            )
            connection.commit()

        stored = connection.execute(
            text("SELECT email FROM users ORDER BY id")
        ).fetchall()
        assert [row[0] for row in stored] == [
            "owner@example.com",
        ]

        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.downgrade()
        connection.commit()

        connection.execute(
            text(
                "INSERT INTO users (id, email) "
                "VALUES (2, 'Owner@Example.com')"
            )
        )
        connection.commit()
        restored = connection.execute(
            text("SELECT email FROM users ORDER BY id")
        ).fetchall()
        assert [row[0] for row in restored] == [
            "owner@example.com",
            "Owner@Example.com",
        ]

    engine.dispose()
    clean.dispose()
