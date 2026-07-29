from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization

from app.schemas.user import UserCreate

from app.security import (
    hash_password,
    verify_password,
)


def generate_slug(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace(" ", "-")
    )


def create_user(db: Session, user: UserCreate):

    slug = generate_slug(user.organization_name)

    existing_org = (
        db.query(Organization)
        .filter(Organization.slug == slug)
        .first()
    )

    if existing_org:
        raise ValueError("Organization already exists")

    organization = Organization(
        name=user.organization_name,
        slug=slug,
        is_active=True
    )

    db.add(organization)
    db.commit()
    db.refresh(organization)

    db_user = User(
        name=user.name,
        email=user.email,
        hashed_password=hash_password(user.password),
        role="owner",
        is_active=True,
        organization_id=organization.id
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


def get_user_by_email(
    db: Session,
    email: str
):
    return (
        db.query(User)
        .filter(User.email == email)
        .first()
    )


def authenticate_user(
    db: Session,
    email: str,
    password: str
):
    user = get_user_by_email(db, email)

    if not user:
        return None

    if not verify_password(
        password,
        user.hashed_password
    ):
        return None

    return user