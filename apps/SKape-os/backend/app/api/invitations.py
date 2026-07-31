from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role

from app.schemas.invitation import (
    InvitationCreate,
    InvitationResponse,
)

from app.crud.invitation import (
    create_invitation,
    get_pending_invitation_by_email,
)

router = APIRouter(
    prefix="/invitations",
    tags=["Invitations"]
)


@router.post(
    "/",
    response_model=InvitationResponse
)
def invite_user(
    invitation: InvitationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("owner", "admin")
    )
):
    existing = get_pending_invitation_by_email(
        db=db,
        email=invitation.email,
        organization_id=current_user.organization_id
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A pending invitation already exists for this email."
        )

    return create_invitation(
        db=db,
        invitation=invitation,
        organization_id=current_user.organization_id
    )