from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
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

from app.schemas.invitation import (
    InvitationAccept,
    InvitationCreate,
    InvitationJoin,
    InvitationResponse,
)


router = APIRouter(
    prefix="/invitations",
    tags=["Invitations"],
)


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

    # =========================================================
    # CHECK IF USER IS ALREADY A MEMBER
    # =========================================================

    existing_user = (
        db.query(User)
        .filter(
            User.email == email,
            User.organization_id
            == current_user.organization_id,
        )
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail=(
                "This user is already a member "
                "of your organization."
            ),
        )

    # =========================================================
    # CHECK EXISTING PENDING INVITATION
    # =========================================================

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

    # =========================================================
    # CREATE INVITATION
    # =========================================================

    try:
        return create_invitation(
            db,
            InvitationCreate(
                email=email,
                role=invitation.role,
            ),
            current_user.organization_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

@router.get(
    "/",
    response_model=List[InvitationResponse],
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
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "message": "Invitation revoked successfully."
    }


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
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


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

    if invitation.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Invitation has already been used.",
        )

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

    if not request.name.strip():
        raise HTTPException(
            status_code=400,
            detail="Name is required.",
        )

    if len(request.password) < 8:
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must contain at least "
                "8 characters."
            ),
        )

    try:
        user = create_user_from_invitation(
            db,
            invitation,
            request.name.strip(),
            request.password,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return {
        "message": "Invitation accepted successfully.",
        "user_id": user.id,
        "organization_id": user.organization_id,
        "role": user.role,
    }


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

    if invitation.status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Invitation has already been used.",
        )

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

    if current_user.email.lower() != invitation.email.lower():
        raise HTTPException(
            status_code=403,
            detail=(
                "This invitation was sent to a different "
                "email address."
            ),
        )

    current_user.organization_id = (
        invitation.organization_id
    )

    current_user.role = invitation.role

    invitation.status = "accepted"

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Invitation accepted successfully.",
        "user_id": current_user.id,
        "organization_id": current_user.organization_id,
        "role": current_user.role,
    }