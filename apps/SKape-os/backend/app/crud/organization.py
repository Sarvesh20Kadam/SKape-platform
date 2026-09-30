import re

from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
)
from app.crud.activity import log_activity


# ============================================================
# Helpers
# ============================================================

def generate_slug(
    db: Session,
    name: str,
) -> str:
    """
    Generate a unique organization slug from the organization name.
    """

    base_slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        name.lower().strip(),
    ).strip("-")

    if not base_slug:
        base_slug = "organization"

    slug = base_slug
    counter = 2

    while (
        db.query(Organization)
        .filter(Organization.slug == slug)
        .first()
        is not None
    ):
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


# ============================================================
# Create
# ============================================================

def create_organization(
    db: Session,
    organization: OrganizationCreate,
    user_id: int | None = None,
):
    """
    Create an organization with a server-generated unique slug.

    If user_id is provided, record the organization creation
    in the activity log.
    """

    slug = generate_slug(
        db,
        organization.name,
    )

    db_org = Organization(
        **organization.model_dump(),
        slug=slug,
    )

    db.add(db_org)

    # Get database-generated ID before activity logging.
    db.flush()

    # --------------------------------------------------------
    # Activity log
    # --------------------------------------------------------

    if user_id is not None:
        log_activity(
            db=db,
            action="created",
            entity="organization",
            entity_id=db_org.id,
            user_id=user_id,
            organization_id=db_org.id,
        )

    db.commit()
    db.refresh(db_org)

    return db_org


# ============================================================
# Read
# ============================================================

def get_organizations(
    db: Session,
):
    return (
        db.query(Organization)
        .all()
    )


def get_organization_by_id(
    db: Session,
    organization_id: int,
):
    return (
        db.query(Organization)
        .filter(
            Organization.id == organization_id
        )
        .first()
    )


def get_organization_by_slug(
    db: Session,
    slug: str,
):
    return (
        db.query(Organization)
        .filter(
            Organization.slug == slug
        )
        .first()
    )


# ============================================================
# Update
# ============================================================

def update_organization(
    db: Session,
    organization_id: int,
    organization: OrganizationUpdate,
    user_id: int | None = None,
):
    db_org = get_organization_by_id(
        db,
        organization_id,
    )

    if db_org is None:
        return None

    update_data = organization.model_dump(
        exclude_unset=True
    )

    for key, value in update_data.items():

        if key == "name":
            value = value.strip()

            if not value:
                raise ValueError(
                    "Organization name cannot be empty."
                )

        setattr(
            db_org,
            key,
            value,
        )

    # --------------------------------------------------------
    # Activity log
    # --------------------------------------------------------

    if user_id is not None:
        log_activity(
            db=db,
            action="updated",
            entity="organization",
            entity_id=db_org.id,
            user_id=user_id,
            organization_id=db_org.id,
        )

    db.commit()
    db.refresh(db_org)

    return db_org


# ============================================================
# Delete
# ============================================================

def delete_organization(
    db: Session,
    organization_id: int,
    user_id: int | None = None,
):
    db_org = get_organization_by_id(
        db,
        organization_id,
    )

    if db_org is None:
        return None

    deleted_organization_id = db_org.id

    # --------------------------------------------------------
    # Activity log
    #
    # Must happen BEFORE deletion because the activity record
    # still needs the organization context.
    # --------------------------------------------------------

    if user_id is not None:
        log_activity(
            db=db,
            action="deleted",
            entity="organization",
            entity_id=deleted_organization_id,
            user_id=user_id,
            organization_id=deleted_organization_id,
        )

    db.delete(db_org)
    db.commit()

    return db_org


# ============================================================
# Organization Members
# ============================================================

def get_organization_members(
    db: Session,
    organization_id: int,
):
    return (
        db.query(User)
        .filter(
            User.organization_id == organization_id
        )
        .all()
    )