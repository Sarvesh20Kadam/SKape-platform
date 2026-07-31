from datetime import datetime, timedelta
import secrets

from sqlalchemy.orm import Session

from app.models.invitation import Invitation
from app.schemas.invitation import InvitationCreate


def create_invitation(
    db: Session,
    invitation: InvitationCreate,
    organization_id: int
):
    token = secrets.token_urlsafe(32)

    expires_at = datetime.utcnow() + timedelta(days=7)

    db_invitation = Invitation(
        email=invitation.email,
        token=token,
        role=invitation.role,
        organization_id=organization_id,
        expires_at=expires_at
    )

    db.add(db_invitation)
    db.commit()
    db.refresh(db_invitation)

    return db_invitation


def get_pending_invitation_by_email(
    db: Session,
    email: str,
    organization_id: int
):
    return (
        db.query(Invitation)
        .filter(
            Invitation.email == email,
            Invitation.organization_id == organization_id,
            Invitation.status == "pending"
        )
        .first()
    )