"""API workflows that the focused security tests do not connect."""

PASSWORD = "Correct-horse-1"


def _register(api, email, organization):
    response = api.post(
        "/api/v1/users/",
        json={
            "name": "Workflow User",
            "email": email,
            "password": PASSWORD,
            "organization_name": organization,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


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


def _detail(response):
    return response.json().get("detail", response.text)


def test_invitation_role_change_and_membership_workflow(api):
    owner = _register(api, "flow-owner@example.com", "Flow Org")
    outsider = _register(
        api,
        "flow-outsider@example.com",
        "Other Flow Org",
    )
    owner_headers = _auth(api, owner["email"])
    outsider_headers = _auth(api, outsider["email"])

    me = api.get("/api/v1/users/me", headers=owner_headers)
    assert me.status_code == 200
    assert me.json()["role"] == "owner"
    assert me.json()["id"] == owner["id"]

    members = api.get(
        "/api/v1/organizations/members",
        headers=owner_headers,
    )
    assert members.status_code == 200
    assert {item["email"] for item in members.json()} == {
        owner["email"]
    }

    invited = api.post(
        "/api/v1/invitations/",
        headers=owner_headers,
        json={
            "email": "flow-member@example.com",
            "role": "employee",
        },
    )
    assert invited.status_code == 200
    token = invited.json()["token"]

    accepted = api.post(
        "/api/v1/invitations/accept",
        json={
            "token": token,
            "name": "Flow Member",
            "password": PASSWORD,
        },
    )
    assert accepted.status_code == 200
    member = accepted.json()
    assert member["role"] == "employee"
    assert member["user_id"] != owner["id"]

    reused = api.post(
        "/api/v1/invitations/accept",
        json={
            "token": token,
            "name": "Flow Member",
            "password": PASSWORD,
        },
    )
    assert reused.status_code == 400
    assert _detail(reused) == "Invitation has already been used."

    member_headers = _auth(api, "flow-member@example.com")
    denied = api.post(
        "/api/v1/projects/",
        headers=member_headers,
        json={
            "name": "Blocked",
            "description": "Employees cannot create projects.",
        },
    )
    assert denied.status_code == 403

    promoted = api.patch(
        f"/api/v1/users/{member['user_id']}/role",
        headers=owner_headers,
        json={"role": "manager"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "manager"

    created = api.post(
        "/api/v1/projects/",
        headers=member_headers,
        json={
            "name": "Operations",
            "description": "Plant operations.",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["id"]

    hidden = api.get(
        f"/api/v1/projects/{project_id}",
        headers=outsider_headers,
    )
    assert hidden.status_code == 404

    roster = api.get(
        "/api/v1/organizations/members",
        headers=member_headers,
    )
    assert {item["email"] for item in roster.json()} == {
        owner["email"],
        "flow-member@example.com",
    }
    outsider_roster = api.get(
        "/api/v1/organizations/members",
        headers=outsider_headers,
    )
    assert outsider["email"] in {
        item["email"] for item in outsider_roster.json()
    }
    assert owner["email"] not in {
        item["email"] for item in outsider_roster.json()
    }


def test_project_task_comment_and_activity_workflow(api):
    owner = _register(api, "work-owner@example.com", "Work Org")
    outsider = _register(
        api,
        "work-outsider@example.com",
        "Outside Work Org",
    )
    headers = _auth(api, owner["email"])
    outsider_headers = _auth(api, outsider["email"])

    project = api.post(
        "/api/v1/projects/",
        headers=headers,
        json={
            "name": "Line 1",
            "description": "First production line.",
        },
    )
    assert project.status_code == 200
    project_id = project.json()["id"]

    other_project = api.post(
        "/api/v1/projects/",
        headers=outsider_headers,
        json={
            "name": "Foreign",
            "description": "Another tenant.",
        },
    )
    assert other_project.status_code == 200

    foreign_assignee = api.post(
        "/api/v1/tasks/",
        headers=headers,
        json={
            "title": "Cross assignee",
            "project_id": project_id,
            "assigned_to": outsider["id"],
            "priority": "low",
        },
    )
    assert foreign_assignee.status_code == 400
    assert "organization" in _detail(foreign_assignee).lower()

    task = api.post(
        "/api/v1/tasks/",
        headers=headers,
        json={
            "title": "Inspect line",
            "description": "Morning inspection.",
            "project_id": project_id,
            "assigned_to": owner["id"],
            "priority": "high",
        },
    )
    assert task.status_code == 200
    task_id = task.json()["id"]
    assert task.json()["assigned_to"] == owner["id"]
    assert task.json()["status"] == "todo"

    moved = api.put(
        f"/api/v1/tasks/{task_id}",
        headers=headers,
        json={"project_id": other_project.json()["id"]},
    )
    assert moved.status_code == 400

    invalid_status = api.put(
        f"/api/v1/tasks/{task_id}",
        headers=headers,
        json={"status": "archived"},
    )
    assert invalid_status.status_code == 422

    completed = api.put(
        f"/api/v1/tasks/{task_id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    comment = api.post(
        "/api/v1/comments/",
        headers=headers,
        json={
            "content": "Inspection finished.",
            "task_id": task_id,
        },
    )
    assert comment.status_code == 200

    hidden_task = api.get(
        f"/api/v1/tasks/{task_id}",
        headers=outsider_headers,
    )
    hidden_comments = api.get(
        f"/api/v1/comments/{task_id}",
        headers=outsider_headers,
    )
    assert hidden_task.status_code == 404
    assert hidden_comments.status_code == 200
    assert hidden_comments.json() == []

    activity = api.get(
        "/api/v1/activities/",
        headers=headers,
    )
    assert activity.status_code == 200
    actions = {
        (item["entity"], item["action"])
        for item in activity.json()
    }
    assert ("project", "created") in actions
    assert ("task", "created") in actions
    assert ("task", "updated") in actions
    assert ("comment", "created") in actions

    dashboard = api.get(
        "/api/v1/dashboard/",
        headers=headers,
    )
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["total_projects"] == 1
    assert body["total_tasks"] == 1
    assert body["completed_tasks"] == 1
    assert body["pending_tasks"] == 0
    assert body["total_members"] == 1

    other_dashboard = api.get(
        "/api/v1/dashboard/",
        headers=outsider_headers,
    )
    assert other_dashboard.json()["total_projects"] == 1
    assert other_dashboard.json()["total_tasks"] == 0


def test_asset_assignment_stays_inside_the_organization(api):
    owner = _register(api, "asset-owner@example.com", "Asset Org")
    outsider = _register(
        api,
        "asset-outsider@example.com",
        "Asset Outside",
    )
    headers = _auth(api, owner["email"])
    outsider_headers = _auth(api, outsider["email"])

    foreign_user = api.post(
        "/api/v1/assets/",
        headers=headers,
        json={
            "name": "Foreign pump",
            "asset_type": "pump",
            "assigned_to": outsider["id"],
        },
    )
    assert foreign_user.status_code == 400

    asset = api.post(
        "/api/v1/assets/",
        headers=headers,
        json={
            "name": "Line pump",
            "asset_type": "pump",
            "assigned_to": owner["id"],
            "location": "Bay 2",
        },
    )
    assert asset.status_code == 200
    asset_id = asset.json()["id"]
    assert asset.json()["assigned_to"] == owner["id"]
    assert asset.json()["organization_id"] > 0

    hidden = api.get(
        f"/api/v1/assets/{asset_id}",
        headers=outsider_headers,
    )
    assert hidden.status_code == 404

    other_asset = api.post(
        "/api/v1/assets/",
        headers=outsider_headers,
        json={
            "name": "Other pump",
            "asset_type": "pump",
        },
    )
    assert other_asset.status_code == 200

    device = api.post(
        "/api/v1/devices/",
        headers=headers,
        json={
            "device_id": "asset-pump-01",
            "name": "Pump sensor",
            "device_type": "sensor",
            "asset_id": asset_id,
        },
    )
    assert device.status_code == 200
    assert device.json()["asset_id"] == asset_id

    foreign_asset = api.post(
        "/api/v1/devices/",
        headers=headers,
        json={
            "device_id": "asset-pump-02",
            "name": "Stolen link",
            "device_type": "sensor",
            "asset_id": other_asset.json()["id"],
        },
    )
    assert foreign_asset.status_code == 400

    hidden_device = api.get(
        f"/api/v1/devices/{device.json()['id']}",
        headers=outsider_headers,
    )
    assert hidden_device.status_code == 404


def test_device_alert_resolution_and_maintenance_workflow(api):
    owner = _register(api, "alert-owner@example.com", "Alert Org")
    outsider = _register(
        api,
        "alert-outsider@example.com",
        "Alert Outside",
    )
    headers = _auth(api, owner["email"])
    outsider_headers = _auth(api, outsider["email"])

    project = api.post(
        "/api/v1/projects/",
        headers=headers,
        json={
            "name": "Maintenance",
            "description": "Alert follow-up.",
        },
    )
    assert project.status_code == 200
    project_id = project.json()["id"]
    other_project = api.post(
        "/api/v1/projects/",
        headers=outsider_headers,
        json={
            "name": "Foreign maintenance",
            "description": "Other tenant.",
        },
    )
    assert other_project.status_code == 200

    created = api.post(
        "/api/v1/devices/",
        headers=headers,
        json={
            "device_id": "alert-pump-01",
            "name": "Alert pump",
            "device_type": "sensor",
        },
    )
    assert created.status_code == 200
    device_pk = created.json()["id"]
    provisioned = api.post(
        f"/api/v1/devices/{device_pk}/credentials",
        headers=headers,
    )
    assert provisioned.status_code == 200
    device_headers = {
        "X-Device-ID": "alert-pump-01",
        "X-Device-Secret": provisioned.json()["device_secret"],
    }

    telemetry = api.post(
        f"/api/v1/devices/{device_pk}/telemetry",
        headers=device_headers,
        json={"temperature": 55},
    )
    assert telemetry.status_code == 200
    assert telemetry.json()["temperature"] == 55

    health = api.get(
        f"/api/v1/devices/{device_pk}/health",
        headers=headers,
    )
    detail = api.get(
        f"/api/v1/devices/{device_pk}/detail",
        headers=headers,
    )
    assert health.status_code == 200
    assert health.json()["device_status"] == "online"
    assert detail.status_code == 200
    assert detail.json()["device"]["id"] == device_pk
    assert detail.json()["latest_telemetry"]["temperature"] == 55

    hidden_detail = api.get(
        f"/api/v1/devices/{device_pk}/detail",
        headers=outsider_headers,
    )
    assert hidden_detail.status_code == 404

    alerts = api.get(
        "/api/v1/alerts/",
        headers=headers,
        params={"unresolved_only": True},
    )
    assert alerts.status_code == 200
    matches = [
        item
        for item in alerts.json()
        if item["alert_type"] == "high_temperature"
    ]
    assert len(matches) == 1
    alert_id = matches[0]["id"]

    hidden_alert = api.get(
        f"/api/v1/alerts/{alert_id}",
        headers=outsider_headers,
    )
    assert hidden_alert.status_code == 404

    foreign_task = api.post(
        f"/api/v1/alerts/{alert_id}/maintenance-task",
        headers=headers,
        params={"project_id": other_project.json()["id"]},
    )
    assert foreign_task.status_code == 400

    maintenance = api.post(
        f"/api/v1/alerts/{alert_id}/maintenance-task",
        headers=headers,
        params={"project_id": project_id},
    )
    assert maintenance.status_code == 200
    assert maintenance.json()["alert_id"] == alert_id
    assert maintenance.json()["project_id"] == project_id
    assert maintenance.json()["title"] == "Maintenance: High Temperature"

    duplicate = api.post(
        f"/api/v1/alerts/{alert_id}/maintenance-task",
        headers=headers,
        params={"project_id": project_id},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == maintenance.json()["id"]

    outsider_task = api.post(
        f"/api/v1/alerts/{alert_id}/maintenance-task",
        headers=outsider_headers,
        params={"project_id": other_project.json()["id"]},
    )
    assert outsider_task.status_code == 404

    resolved = api.patch(
        f"/api/v1/alerts/{alert_id}/resolve",
        headers=headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["is_resolved"] is True

    again = api.patch(
        f"/api/v1/alerts/{alert_id}/resolve",
        headers=headers,
    )
    assert again.status_code == 200
    assert again.json()["is_resolved"] is True

    remaining = api.get(
        "/api/v1/alerts/",
        headers=headers,
        params={"unresolved_only": True},
    )
    assert all(
        item["id"] != alert_id for item in remaining.json()
    )

    activity = api.get("/api/v1/activities/", headers=headers)
    actions = {
        (item["entity"], item["action"])
        for item in activity.json()
    }
    assert ("alert", "resolved") in actions
    assert ("task", "created") in actions
    assert ("device", "created") in actions
