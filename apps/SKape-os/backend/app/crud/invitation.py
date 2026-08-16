from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy.orm import Session

from app.models.invitation import Invitation
from app.models.user import User
from app.schemas.invitation import InvitationCreate
from app.security import hash_password


ALLOWED_INVITATION_ROLES = {
    "admin",
    "manager",
    "employee",
}


def create_invitation(
    db: Session,
    invitation: InvitationCreate,
    organization_id: int,
):
    if invitation.role not in ALLOWED_INVITATION_ROLES:
        raise ValueError("Invalid invitation role.")

    token = secrets.token_urlsafe(32)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=7)
    )

    db_invitation = Invitation(
        email=invitation.email,
        token=token,
        role=invitation.role,
        organization_id=organization_id,
        status="pending",
        expires_at=expires_at,
    )

    db.add(db_invitation)
    db.commit()
    db.refresh(db_invitation)

    return db_invitation


def get_pending_invitation_by_email(
    db: Session,
    email: str,
    organization_id: int,
):
    return (
        db.query(Invitation)
        .filter(
            Invitation.email.ilike(email),
            Invitation.organization_id == organization_id,
            Invitation.status == "pending",
        )
        .first()
    )


def get_organization_invitations(
    db: Session,
    organization_id: int,
):
    return (
        db.query(Invitation)
        .filter(
    Invitation.organization_id == organization_id,
)
        .order_by(
            Invitation.created_at.desc()
        )
        .all()
    )


def get_invitation_by_token(
    db: Session,
    token: str,
):
    return (
        db.query(Invitation)
        .filter(
            Invitation.token == token,
        )
        .first()
    )


def revoke_invitation(
    db: Session,
    invitation: Invitation,
):
    if invitation.status == "accepted":
        raise ValueError(
            "An accepted invitation cannot be revoked."
        )

    if invitation.status == "revoked":
        raise ValueError(
            "Invitation has already been revoked."
        )

    invitation.status = "revoked"

    db.commit()
    db.refresh(invitation)

    return invitation


def resend_invitation(
    db: Session,
    invitation: Invitation,
):
    if invitation.status == "accepted":
        raise ValueError(
            "An accepted invitation cannot be resent."
        )

    invitation.token = secrets.token_urlsafe(32)

    invitation.expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=7)
    )

    invitation.status = "pending"

    db.commit()
    db.refresh(invitation)

    return invitation


def create_user_from_invitation(
    db: Session,
    invitation: Invitation,
    name: str,
    password: str,
):
    existing_user = (
        db.query(User)
        .filter(
            User.email == invitation.email,
        )
        .first()
    )

    if existing_user:
        raise ValueError(
            "A user with this email already exists."
        )

    user = User(
        name=name,
        email=invitation.email,
        hashed_password=hash_password(password),
        role=invitation.role,
        organization_id=invitation.organization_id,
        is_active=True,
    )

    db.add(user)

    invitation.status = "accepted"

    db.commit()
    db.refresh(user)

    return user