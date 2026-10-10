import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault(
    "SECRET_KEY",
    "skape-test-jwt-signing-secret-value",
)
os.environ.setdefault("ALGORITHM", "HS256")

import pytest
from pydantic import ValidationError

import app.models  # noqa: F401
from app.crud.activity import log_activity as write_activity
from app.crud.comment import (
    create_comment,
    delete_comment,
    get_comments,
    update_comment,
)
from app.dependencies import get_current_user
from app.exceptions import ForbiddenException
from app.main import app
from app.models.activity import Activity
from app.models.comment import Comment
from app.models.organization import Organization
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentUpdate


def _org(db, name, slug):
    org = Organization(
        name=name,
        slug=slug,
        is_active=True,
    )
    db.add(org)
    db.flush()
    return org


def _user(db, org, role, email):
    user = User(
        name=role,
        email=email,
        hashed_password="test-hash",
        role=role,
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    db.flush()
    return user


def _task(db, org, title):
    project = Project(
        name=title,
        organization_id=org.id,
        status="active",
    )
    db.add(project)
    db.flush()

    task = Task(
        title=title,
        project_id=project.id,
        organization_id=org.id,
        status="todo",
        priority="medium",
    )
    db.add(task)
    db.flush()
    return task


def _actor(user):
    return SimpleNamespace(
        id=user.id,
        organization_id=user.organization_id,
        role=user.role,
    )


@pytest.fixture
def world(db):
    org_a = _org(db, "Org A", "org-a")
    org_b = _org(db, "Org B", "org-b")

    users = {
        "owner": _user(db, org_a, "owner", "owner@example.com"),
        "admin": _user(db, org_a, "admin", "admin@example.com"),
        "manager": _user(db, org_a, "manager", "manager@example.com"),
        "employee": _user(
            db,
            org_a,
            "employee",
            "employee@example.com",
        ),
        "other_owner": _user(
            db,
            org_b,
            "owner",
            "other-owner@example.com",
        ),
    }

    task = _task(db, org_a, "Task A")
    other_task = _task(db, org_b, "Task B")
    db.commit()

    return SimpleNamespace(
        org_a=org_a.id,
        org_b=org_b.id,
        task=task.id,
        other_task=other_task.id,
        users={
            role: _actor(user)
            for role, user in users.items()
        },
    )


def _as(actor):
    def override_current_user():
        return actor

    app.dependency_overrides[get_current_user] = (
        override_current_user
    )


def _activities(session, comment_id):
    return (
        session.query(Activity)
        .filter(
            Activity.entity == "comment",
            Activity.entity_id == comment_id,
        )
        .all()
    )


def _error_text(response):
    body = response.json()
    detail = body.get("detail", body.get("message", body))
    return str(detail)


def _stamp(session_factory, comment_ids):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    session = session_factory()
    try:
        for index, comment_id in enumerate(comment_ids):
            comment = session.get(Comment, comment_id)
            comment.created_at = start + timedelta(minutes=index)
        session.commit()
    finally:
        session.close()


def test_schema_rejects_blank_and_overlong_content():
    with pytest.raises(ValidationError):
        CommentCreate(content="", task_id=1)

    with pytest.raises(ValidationError) as blank:
        CommentCreate(content="   ", task_id=1)

    assert "cannot be empty" in str(blank.value)

    with pytest.raises(ValidationError):
        CommentUpdate(content="x" * 2001)

    created = CommentCreate(
        content="  kept  ",
        task_id=1,
    )
    assert created.content == "kept"
    assert len(CommentUpdate(content="x" * 2000).content) == 2000


def test_create_update_delete_and_audit(db, world):
    owner = world.users["owner"]

    created = create_comment(
        db=db,
        comment=CommentCreate(
            content="  first note  ",
            task_id=world.task,
        ),
        user_id=owner.id,
        organization_id=owner.organization_id,
    )

    assert created.content == "first note"
    assert created.organization_id == world.org_a
    assert created.user_id == owner.id
    assert created.id is not None

    created_activity = _activities(db, created.id)
    assert len(created_activity) == 1
    assert created_activity[0].action == "created"
    assert created_activity[0].entity_id == created.id
    assert created_activity[0].organization_id == world.org_a
    assert created_activity[0].user_id == owner.id

    updated = update_comment(
        db=db,
        comment_id=created.id,
        organization_id=world.org_a,
        user_id=world.users["admin"].id,
        user_role="admin",
        updated_comment=CommentUpdate(content=" revised "),
    )

    assert updated.content == "revised"
    actions = sorted(
        item.action for item in _activities(db, created.id)
    )
    assert actions == ["created", "updated"]

    deleted = delete_comment(
        db=db,
        comment_id=created.id,
        organization_id=world.org_a,
        user_id=world.users["owner"].id,
        user_role="owner",
    )

    assert deleted.content == "revised"
    assert deleted.id == created.id
    assert db.get(Comment, created.id) is None
    actions = sorted(
        item.action for item in _activities(db, created.id)
    )
    assert actions == ["created", "deleted", "updated"]


def test_edit_permissions(db, world):
    author = world.users["employee"]
    comment = create_comment(
        db=db,
        comment=CommentCreate(
            content="mine",
            task_id=world.task,
        ),
        user_id=author.id,
        organization_id=author.organization_id,
    )

    for role in ("owner", "admin"):
        updated = update_comment(
            db=db,
            comment_id=comment.id,
            organization_id=world.org_a,
            user_id=world.users[role].id,
            user_role=role,
            updated_comment=CommentUpdate(
                content=f"edited by {role}",
            ),
        )
        assert updated.content == f"edited by {role}"

    for role in ("manager", "employee"):
        with pytest.raises(ForbiddenException) as denied:
            update_comment(
                db=db,
                comment_id=comment.id,
                organization_id=world.org_a,
                user_id=world.users["owner"].id,
                user_role=role,
                updated_comment=CommentUpdate(content="nope"),
            )

        assert denied.value.status_code == 403
        assert comment.content == "edited by admin"

    own = update_comment(
        db=db,
        comment_id=comment.id,
        organization_id=world.org_a,
        user_id=author.id,
        user_role="employee",
        updated_comment=CommentUpdate(content="employee edit"),
    )
    assert own.content == "employee edit"


def test_cross_organization_isolation(db, world):
    owner = world.users["owner"]
    other = world.users["other_owner"]

    comment = create_comment(
        db=db,
        comment=CommentCreate(
            content="private",
            task_id=world.task,
        ),
        user_id=owner.id,
        organization_id=owner.organization_id,
    )

    with pytest.raises(ValueError, match="this organization"):
        create_comment(
            db=db,
            comment=CommentCreate(
                content="intrusion",
                task_id=world.task,
            ),
            user_id=other.id,
            organization_id=other.organization_id,
        )

    assert get_comments(
        db=db,
        task_id=world.task,
        organization_id=world.org_b,
    ) == []

    assert update_comment(
        db=db,
        comment_id=comment.id,
        organization_id=world.org_b,
        user_id=other.id,
        user_role="owner",
        updated_comment=CommentUpdate(content="changed"),
    ) is None

    assert delete_comment(
        db=db,
        comment_id=comment.id,
        organization_id=world.org_b,
        user_id=other.id,
        user_role="owner",
    ) is None

    stored = db.get(Comment, comment.id)
    assert stored.content == "private"
    assert stored.organization_id == world.org_a

    rogue = Comment(
        content="mistagged",
        task_id=world.task,
        user_id=other.id,
        organization_id=world.org_b,
    )
    db.add(rogue)
    db.commit()

    visible = get_comments(
        db=db,
        task_id=world.task,
        organization_id=world.org_a,
    )
    assert [item.content for item in visible] == ["private"]


def test_pagination_orders_and_limits(db, world, session_factory):
    owner = world.users["owner"]
    comment_ids = []

    for index in range(4):
        comment = create_comment(
            db=db,
            comment=CommentCreate(
                content=f"note {index}",
                task_id=world.task,
            ),
            user_id=owner.id,
            organization_id=owner.organization_id,
        )
        comment_ids.append(comment.id)

    _stamp(session_factory, comment_ids)
    db.expire_all()

    page = get_comments(
        db=db,
        task_id=world.task,
        organization_id=world.org_a,
        skip=1,
        limit=2,
    )

    assert [item.content for item in page] == [
        "note 1",
        "note 2",
    ]

    assert get_comments(
        db=db,
        task_id=999999,
        organization_id=world.org_a,
    ) == []


def test_audit_failure_rolls_back_create_update_and_delete(
    db,
    world,
    session_factory,
    monkeypatch,
):
    owner = world.users["owner"]

    def fail_after_audit(**kwargs):
        write_activity(**kwargs)
        raise RuntimeError("audit failed")

    monkeypatch.setattr(
        "app.crud.comment.log_activity",
        fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        create_comment(
            db=db,
            comment=CommentCreate(
                content="should vanish",
                task_id=world.task,
            ),
            user_id=owner.id,
            organization_id=owner.organization_id,
        )

    check = session_factory()
    try:
        assert check.query(Comment).count() == 0
        assert check.query(Activity).count() == 0
    finally:
        check.close()

    monkeypatch.undo()

    comment = create_comment(
        db=db,
        comment=CommentCreate(
            content="keep me",
            task_id=world.task,
        ),
        user_id=owner.id,
        organization_id=owner.organization_id,
    )

    monkeypatch.setattr(
        "app.crud.comment.log_activity",
        fail_after_audit,
    )

    with pytest.raises(RuntimeError, match="audit failed"):
        update_comment(
            db=db,
            comment_id=comment.id,
            organization_id=world.org_a,
            user_id=owner.id,
            user_role="owner",
            updated_comment=CommentUpdate(content="changed"),
        )

    with pytest.raises(RuntimeError, match="audit failed"):
        delete_comment(
            db=db,
            comment_id=comment.id,
            organization_id=world.org_a,
            user_id=owner.id,
            user_role="owner",
        )

    check = session_factory()
    try:
        stored = check.get(Comment, comment.id)
        assert stored.content == "keep me"
        actions = [
            item.action for item in _activities(check, comment.id)
        ]
        assert actions == ["created"]
    finally:
        check.close()


def test_blank_update_is_rejected_without_a_write(db, world):
    owner = world.users["owner"]
    comment = create_comment(
        db=db,
        comment=CommentCreate(
            content="stable",
            task_id=world.task,
        ),
        user_id=owner.id,
        organization_id=owner.organization_id,
    )

    with pytest.raises(ValueError, match="cannot be empty"):
        update_comment(
            db=db,
            comment_id=comment.id,
            organization_id=world.org_a,
            user_id=owner.id,
            user_role="owner",
            updated_comment=CommentUpdate.model_construct(
                content="   ",
            ),
        )

    assert db.get(Comment, comment.id).content == "stable"


def test_api_crud_validation_and_tenant_boundaries(
    api,
    world,
    session_factory,
):
    _as(world.users["employee"])

    created = api.post(
        "/api/v1/comments/",
        json={
            "content": "  hello  ",
            "task_id": world.task,
            "organization_id": world.org_b,
            "user_id": world.users["owner"].id,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["content"] == "hello"
    assert body["organization_id"] == world.org_a
    assert body["user_id"] == world.users["employee"].id
    comment_id = body["id"]

    blank = api.post(
        "/api/v1/comments/",
        json={"content": "   ", "task_id": world.task},
    )
    assert blank.status_code == 422
    assert "cannot be empty" in _error_text(blank)

    too_long = api.post(
        "/api/v1/comments/",
        json={
            "content": "x" * 2001,
            "task_id": world.task,
        },
    )
    assert too_long.status_code == 422

    missing_task = api.post(
        "/api/v1/comments/",
        json={"content": "orphan"},
    )
    assert missing_task.status_code == 422

    cross_create = api.post(
        "/api/v1/comments/",
        json={
            "content": "nope",
            "task_id": world.other_task,
        },
    )
    assert cross_create.status_code == 400
    assert "this organization" in _error_text(cross_create)

    _as(world.users["other_owner"])
    hidden = api.get(f"/api/v1/comments/{world.task}")
    assert hidden.status_code == 200
    assert hidden.json() == []

    cross_update = api.put(
        f"/api/v1/comments/{comment_id}",
        json={"content": "hijack"},
    )
    assert cross_update.status_code == 404
    assert "Comment not found" in _error_text(cross_update)

    cross_delete = api.delete(f"/api/v1/comments/{comment_id}")
    assert cross_delete.status_code == 404

    _as(world.users["manager"])
    denied = api.put(
        f"/api/v1/comments/{comment_id}",
        json={"content": "manager edit"},
    )
    assert denied.status_code == 403
    assert "only edit your own" in _error_text(denied)

    _as(world.users["owner"])
    edited = api.put(
        f"/api/v1/comments/{comment_id}?skip=-1&limit=0",
        json={"content": " owner edit "},
    )
    assert edited.status_code == 200
    assert edited.json()["content"] == "owner edit"

    _as(world.users["manager"])
    manager_delete = api.delete(
        f"/api/v1/comments/{comment_id}",
    )
    assert manager_delete.status_code == 403
    assert "only delete your own" in _error_text(manager_delete)

    _as(world.users["employee"])
    deleted = api.delete(f"/api/v1/comments/{comment_id}")
    assert deleted.status_code == 200
    assert deleted.json()["content"] == "owner edit"
    assert deleted.json()["id"] == comment_id

    _as(world.users["owner"])
    listing = api.get(f"/api/v1/comments/{world.task}")
    assert listing.status_code == 200
    assert listing.json() == []

    check = session_factory()
    try:
        assert check.get(Comment, comment_id) is None
        actions = sorted(
            item.action
            for item in _activities(check, comment_id)
        )
        assert actions == ["created", "deleted", "updated"]
        assert all(
            item.organization_id == world.org_a
            for item in _activities(check, comment_id)
        )
    finally:
        check.close()


@pytest.mark.parametrize(
    ("role", "owns", "expected"),
    [
        ("owner", False, 200),
        ("admin", False, 200),
        ("manager", False, 403),
        ("employee", False, 403),
        ("manager", True, 200),
        ("employee", True, 200),
    ],
)
def test_api_edit_authorization(api, world, role, owns, expected):
    author = world.users[role if owns else "employee"]
    if not owns and role == "employee":
        author = world.users["owner"]

    _as(author)
    created = api.post(
        "/api/v1/comments/",
        json={"content": "seed", "task_id": world.task},
    )
    assert created.status_code == 200
    comment_id = created.json()["id"]

    _as(world.users[role])
    response = api.put(
        f"/api/v1/comments/{comment_id}",
        json={"content": f"{role}-edit"},
    )
    assert response.status_code == expected

    if expected == 200:
        assert response.json()["content"] == f"{role}-edit"


def test_api_pagination_bounds(api, world, session_factory):
    _as(world.users["owner"])
    comment_ids = []

    for index in range(12):
        response = api.post(
            "/api/v1/comments/",
            json={
                "content": f"page {index}",
                "task_id": world.task,
            },
        )
        assert response.status_code == 200
        comment_ids.append(response.json()["id"])

    _stamp(session_factory, comment_ids)

    default_page = api.get(f"/api/v1/comments/{world.task}")
    assert default_page.status_code == 200
    assert len(default_page.json()) == 10
    assert default_page.json()[0]["content"] == "page 0"

    sliced = api.get(
        f"/api/v1/comments/{world.task}",
        params={"skip": 10, "limit": 100},
    )
    assert sliced.status_code == 200
    assert [item["content"] for item in sliced.json()] == [
        "page 10",
        "page 11",
    ]

    for params in (
        {"skip": -1},
        {"limit": 0},
        {"limit": 101},
    ):
        rejected = api.get(
            f"/api/v1/comments/{world.task}",
            params=params,
        )
        assert rejected.status_code == 422


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/v1/comments/"),
        ("get", "/api/v1/comments/1"),
        ("put", "/api/v1/comments/1"),
        ("delete", "/api/v1/comments/1"),
    ],
)
def test_comments_require_authentication(api, method, path):
    app.dependency_overrides.pop(get_current_user, None)
    kwargs = {}
    if method in {"post", "put"}:
        kwargs["json"] = {"content": "x", "task_id": 1}

    response = getattr(api, method)(path, **kwargs)
    assert response.status_code == 401
