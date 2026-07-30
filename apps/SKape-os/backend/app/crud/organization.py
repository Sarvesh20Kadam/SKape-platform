from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
)


def create_organization(
    db: Session,
    organization: OrganizationCreate
):
    db_org = Organization(
        **organization.model_dump()
    )

    db.add(db_org)
    db.commit()
    db.refresh(db_org)

    return db_org


def get_organizations(db: Session):
    return db.query(Organization).all()


def get_organization_by_id(
    db: Session,
    organization_id: int
):
    return (
        db.query(Organization)
        .filter(Organization.id == organization_id)
        .first()
    )


def get_organization_by_slug(
    db: Session,
    slug: str
):
    return (
        db.query(Organization)
        .filter(Organization.slug == slug)
        .first()
    )


def update_organization(
    db: Session,
    organization_id: int,
    organization: OrganizationUpdate
):
    db_org = get_organization_by_id(
        db,
        organization_id
    )

    if db_org is None:
        return None

    update_data = organization.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():
        setattr(
            db_org,
            key,
            value
        )

    db.commit()
    db.refresh(db_org)

    return db_org


def delete_organization(
    db: Session,
    organization_id: int
):
    db_org = get_organization_by_id(
        db,
        organization_id
    )

    if db_org is None:
        return None

    db.delete(db_org)
    db.commit()

    return db_org

from sqlalchemy.orm import Session

from app.models.user import User


def get_organization_members(
    db: Session,
    organization_id: int
):
    return (
        db.query(User)
        .filter(User.organization_id == organization_id)
        .all()
    )