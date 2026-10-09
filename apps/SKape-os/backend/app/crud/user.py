from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization

from app.schemas.user import UserCreate

from app.security import (
    hash_password,
    verify_password,
)

from app.crud.activity import log_activity


ALLOWED_USER_ROLES = {
    "admin",
    "manager",
    "employee",
}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def generate_slug(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace(" ", "-")
    )


def create_user(
    db: Session,
    user: UserCreate,
):
    slug = generate_slug(
        user.organization_name
    )

    existing_org = (
        db.query(Organization)
        .filter(
            Organization.slug == slug
        )
        .first()
    )

    if existing_org:
        raise ValueError(
            "Organization already exists"
        )

    organization = Organization(
        name=user.organization_name,
        slug=slug,
        is_active=True,
    )

    db.add(organization)
    db.flush()

    db_user = User(
        name=user.name,
        email=normalize_email(user.email),
        hashed_password=hash_password(
            user.password
        ),
        role="owner",
        is_active=True,
        organization_id=organization.id,
    )

    db.add(db_user)
    db.flush()

    log_activity(
        db=db,
        action="created",
        entity="organization",
        entity_id=organization.id,
        user_id=db_user.id,
        organization_id=organization.id,
    )

    db.commit()
    db.refresh(db_user)

    return db_user


def get_user_by_email(
    db: Session,
    email: str,
):
    normalized = normalize_email(email)

    if not normalized:
        return None

    return (
        db.query(User)
        .filter(func.lower(User.email) == normalized)
        .order_by(User.id.asc())
        .first()
    )


def authenticate_user(
    db: Session,
    email: str,
    password: str,
):
    user = get_user_by_email(
        db,
        email,
    )

    if not user:
        return None

    if not verify_password(
        password,
        user.hashed_password,
    ):
        return None

    return user


def update_user_role(
    db: Session,
    user: User,
    role: str,
    actor_user_id: int,
):
    if role not in ALLOWED_USER_ROLES:
        raise ValueError(
            "Invalid user role."
        )

    previous_role = user.role

    if previous_role == role:
        return user

    user.role = role

    log_activity(
        db=db,
        action="role_changed",
        entity="user",
        entity_id=user.id,
        user_id=actor_user_id,
        organization_id=user.organization_id,
    )

    db.commit()
    db.refresh(user)

    return user