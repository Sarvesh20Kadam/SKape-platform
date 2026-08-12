from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role

from app.crud.invitation import (
    create_invitation,
    create_user_from_invitation,
    get_invitation_by_token,
    get_pending_invitation_by_email,
)

from app.schemas.invitation import (
    InvitationAccept,
    InvitationCreate,
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
    existing = get_pending_invitation_by_email(
        db,
        invitation.email,
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

    try:
        return create_invitation(
            db,
            invitation,
            current_user.organization_id,
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