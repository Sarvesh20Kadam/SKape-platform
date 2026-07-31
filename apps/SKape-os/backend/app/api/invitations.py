from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.permissions import require_role

from app.database import get_db
from app.crud.invitation import (
    create_invitation,
    get_pending_invitation_by_email,
    get_invitation_by_token,
)
from app.schemas.invitation import (
    InvitationCreate,
    InvitationResponse,
    InvitationAccept,
)

router = APIRouter(prefix="/invitations", tags=["Invitations"])



@router.post("/", response_model=InvitationResponse)
def create_new_invitation(
    invitation: InvitationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("owner", "admin")),
):
    existing = get_pending_invitation_by_email(
        db,
        invitation.email,
        current_user.organization_id,
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A pending invitation already exists for this email.",
        )

    return create_invitation(
        db,
        invitation,
        current_user.organization_id,
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

    if invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Invitation has expired.",
        )

    invitation.status = "accepted"

    db.commit()
    db.refresh(invitation)

    return {
        "message": "Invitation accepted successfully."
    }