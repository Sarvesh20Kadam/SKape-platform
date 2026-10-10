from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_owner_for_organization_recovery,
)
from app.permissions import require_role

from app.crud.organization import (
    get_organization_by_id,
    update_organization,
    delete_organization,
    get_organization_members,
    deactivate_organization,
    activate_organization,
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


# ============================================================
# Create Organization
# ============================================================

@router.post(
    "/",
    response_model=OrganizationResponse,
)
def create(
    organization: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("owner")
    ),
):
    # Registration creates the caller's own organization.
    # This route must not create a second tenant for them.
    raise HTTPException(
        status_code=403,
        detail=(
            "You don't have permission to "
            "perform this action."
        ),
    )


# ============================================================
# Current Organization
# ============================================================

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
        db=db,
        organization_id=current_user.organization_id,
    )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    if not organization.is_active:
        raise HTTPException(
            status_code=403,
            detail="Organization is inactive.",
        )

    return organization


# ============================================================
# Update Current Organization
# ============================================================

@router.put(
    "/current",
    response_model=OrganizationResponse,
)
def update_current_organization(
    organization: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
        )
    ),
):
    try:
        updated = update_organization(
            db=db,
            organization_id=current_user.organization_id,
            organization=organization,
            user_id=current_user.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return updated


# ============================================================
# Organization Members
# ============================================================

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
        db=db,
        organization_id=current_user.organization_id,
    )

# ============================================================
# Deactivate Current Organization
# ============================================================

@router.post(
    "/current/deactivate",
    response_model=OrganizationResponse,
)
def deactivate_current_organization(
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("owner")
    ),
):
    organization = deactivate_organization(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return organization

# ============================================================
# Activate Current Organization
# ============================================================

@router.post(
    "/current/activate",
    response_model=OrganizationResponse,
)
def activate_current_organization(
    db: Session = Depends(get_db),
    current_user=Depends(
        get_owner_for_organization_recovery
    ),
):
    organization = activate_organization(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return organization

# ============================================================
# Get Organization
# ============================================================

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
    if organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this organization.",
        )

    organization = get_organization_by_id(
        db=db,
        organization_id=organization_id,
    )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    if not organization.is_active:
        raise HTTPException(
            status_code=403,
            detail="Organization is inactive.",
        )

    return organization


# ============================================================
# Deactivate Organization
# ============================================================

@router.patch(
    "/{organization_id}/deactivate",
    response_model=OrganizationResponse,
)
def deactivate(
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

    try:
        organization = deactivate_organization(
            db=db,
            organization_id=organization_id,
            user_id=current_user.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return organization


# ============================================================
# Reactivate Organization
# ============================================================

@router.patch(
    "/{organization_id}/reactivate",
    response_model=OrganizationResponse,
)
def reactivate(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        get_owner_for_organization_recovery
    ),
):
    if organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this organization.",
        )

    try:
        organization = activate_organization(
            db=db,
            organization_id=organization_id,
            user_id=current_user.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    if organization is None:
        raise HTTPException(
            status_code=404,
            detail="Organization not found",
        )

    return organization