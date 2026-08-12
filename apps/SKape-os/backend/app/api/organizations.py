from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role

from app.crud.organization import (
    create_organization,
    get_organization_by_id,
    update_organization,
    delete_organization,
    get_organization_members,
)

from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
)

from app.schemas.user import UserResponse


router = APIRouter(
    prefix="/organizations",
    tags=["Organizations"],
)


@router.post(
    "/",
    response_model=OrganizationResponse,
)
def create(
    organization: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("owner")),
):
    return create_organization(
        db,
        organization,
    )


@router.get(
    "/current",
    response_model=OrganizationResponse,
)
def get_current_organization(
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
            "employee",
        )
    ),
):
    organization = get_organization_by_id(
        db,
        current_user.organization_id,
    )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return organization


@router.put(
    "/current",
    response_model=OrganizationResponse,
)
def update_current_organization(
    organization: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("owner", "admin")
    ),
):
    updated = update_organization(
        db,
        current_user.organization_id,
        organization,
    )

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return updated


@router.get(
    "/members",
    response_model=List[UserResponse],
)
def get_members(
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
            "employee",
        )
    ),
):
    return get_organization_members(
        db,
        current_user.organization_id,
    )


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
)
def get_one(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    # Users can only access their own organization.
    if organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this organization.",
        )

    organization = get_organization_by_id(
        db,
        organization_id,
    )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return organization


@router.delete(
    "/{organization_id}",
    response_model=OrganizationResponse,
)
def delete(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("owner")
    ),
):
    if organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this organization.",
        )

    deleted = delete_organization(
        db,
        organization_id,
    )

    if deleted is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return deleted