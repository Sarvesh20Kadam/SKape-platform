from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.invitation import Invitation
from app.permissions import require_role

from app.crud.invitation import (
    create_invitation,
    create_user_from_invitation,
    get_invitation_by_token,
    get_pending_invitation_by_email,
    get_organization_invitations,
    revoke_invitation,
    resend_invitation,
)
from app.crud.user import get_user_by_email
from app.security import validate_password_length

from app.schemas.invitation import (
    InvitationAccept,
    InvitationCreate,
    InvitationJoin,
    InvitationListResponse,
    InvitationResponse,
)


INVITATION_EMAIL_UNAVAILABLE = (
    "This email cannot be invited."
)


router = APIRouter(
    prefix="/invitations",
    tags=["Invitations"],
)


# =========================================================
# CREATE INVITATION
# =========================================================

@router.post(
    "/",
    response_model=InvitationResponse,
)
def create_new_invitation(
    invitation: InvitationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("owner", "admin")
    ),
):
    email = invitation.email.strip().lower()

    if (
        invitation.role == "admin"
        and current_user.role != "owner"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "You don't have permission to "
                "perform this action."
            ),
        )

    # =====================================================
    # CHECK IF USER ALREADY EXISTS
    # =====================================================

    existing_user = get_user_by_email(
        db,
        email,
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail=INVITATION_EMAIL_UNAVAILABLE,
        )

    # =====================================================
    # CHECK EXISTING PENDING INVITATION
    # =====================================================

    existing = get_pending_invitation_by_email(
        db,
        email,
        current_user.organization_id,
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                "A pending invitation already "
                "exists for this email."
            ),
        )

    # =====================================================
    # CREATE INVITATION
    # =====================================================

    try:
        return create_invitation(
            db,
            InvitationCreate(
                email=email,
                role=invitation.role,
            ),
            current_user.organization_id,
            current_user.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# GET ORGANIZATION INVITATIONS
# =========================================================

@router.get(
    "/",
    response_model=List[InvitationListResponse],
)
def get_invitations(
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    return get_organization_invitations(
        db,
        current_user.organization_id,
    )


# =========================================================
# REVOKE INVITATION
# =========================================================

@router.delete(
    "/{invitation_id}"
)
def revoke_invitation_endpoint(
    invitation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("owner", "admin")
    ),
):
    invitation = (
        db.query(Invitation)
        .filter(
            Invitation.id == invitation_id,
            Invitation.organization_id
            == current_user.organization_id,
        )
        .first()
    )

    if invitation is None:
        raise HTTPException(
            status_code=404,
            detail="Invitation not found.",
        )

    try:
        revoke_invitation(
            db,
            invitation,
            current_user.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "message": "Invitation revoked successfully."
    }


# =========================================================
# RESEND INVITATION
# =========================================================

@router.post(
    "/{invitation_id}/resend",
    response_model=InvitationResponse,
)
def resend_invitation_endpoint(
    invitation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("owner", "admin")
    ),
):
    invitation = (
        db.query(Invitation)
        .filter(
            Invitation.id == invitation_id,
            Invitation.organization_id
            == current_user.organization_id,
        )
        .first()
    )

    if invitation is None:
        raise HTTPException(
            status_code=404,
            detail="Invitation not found.",
        )

    try:
        return resend_invitation(
            db,
            invitation,
            current_user.id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# =========================================================
# ACCEPT INVITATION - NEW USER
# =========================================================

@router.post("/accept")
def accept_invitation(
    request: InvitationAccept,
    db: Session = Depends(get_db),
):
    invitation = get_invitation_by_token(
        db,
        request.token,
    )

    if not invitation:
        raise HTTPException(
            status_code=404,
            detail="Invalid invitation token.",
        )

    # =====================================================
    # CHECK INVITATION STATUS
    # =====================================================

    if invitation.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Invitation has already been used.",
        )

    # =====================================================
    # CHECK EXPIRATION
    # =====================================================

    now = datetime.now(timezone.utc)

    expires_at = invitation.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at < now:
        raise HTTPException(
            status_code=400,
            detail="Invitation has expired.",
        )

    # =====================================================
    # CHECK ORGANIZATION LIFECYCLE
    # =====================================================

    organization = invitation.organization

    if (
        organization is None
        or not organization.is_active
    ):
        raise HTTPException(
            status_code=403,
            detail="Organization is inactive",
        )

    # =====================================================
    # VALIDATE NAME
    # =====================================================

    if not request.name.strip():
        raise HTTPException(
            status_code=400,
            detail="Name is required.",
        )

    # =====================================================
    # VALIDATE PASSWORD
    # =====================================================

    try:
        validate_password_length(request.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    # =====================================================
    # CREATE USER
    # =====================================================

    try:
        user = create_user_from_invitation(
            db,
            invitation,
            request.name.strip(),
            request.password,
        )

    except ValueError as exc:
        detail = str(exc)
        status_code = (
            403
            if detail == "Organization is inactive"
            else 400
        )
        raise HTTPException(
            status_code=status_code,
            detail=detail,
        )

    return {
        "message": "Invitation accepted successfully.",
        "user_id": user.id,
        "organization_id": user.organization_id,
        "role": user.role,
    }


# =========================================================
# ACCEPT INVITATION - EXISTING USER
# =========================================================

@router.post("/accept-existing")
def accept_existing_user_invitation(
    request: InvitationJoin,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    invitation = get_invitation_by_token(
        db,
        request.token,
    )

    if not invitation:
        raise HTTPException(
            status_code=404,
            detail="Invalid invitation token.",
        )

    # =====================================================
    # CHECK INVITATION STATUS
    # =====================================================

    if invitation.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Invitation has already been used.",
        )

    # =====================================================
    # CHECK EXPIRATION
    # =====================================================

    now = datetime.now(timezone.utc)

    expires_at = invitation.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at < now:
        raise HTTPException(
            status_code=400,
            detail="Invitation has expired.",
        )

    # =====================================================
    # VERIFY EMAIL
    # =====================================================

    if (
        current_user.email.lower()
        != invitation.email.lower()
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "This invitation was sent to a different "
                "email address."
            ),
        )

    # =====================================================
    # MEMBERSHIP CANNOT CHANGE
    #
    # Authenticated users already belong to one
    # organization. This endpoint does not move them
    # or assign a role from the invitation.
    # =====================================================

    raise HTTPException(
        status_code=409,
        detail=(
            "You already belong to an organization. "
            "Invitations cannot change organization "
            "membership."
        ),
    )