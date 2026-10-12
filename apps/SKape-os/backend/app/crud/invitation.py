from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy.orm import Session

from app.crud.activity import log_activity
from app.crud.user import (
    get_user_by_email,
    normalize_email,
)
from app.models.invitation import Invitation
from app.models.user import User
from app.schemas.invitation import InvitationCreate
from app.security import hash_password


ALLOWED_INVITATION_ROLES = {
    "admin",
    "manager",
    "employee",
}


def _commit_with_audit(
    db: Session,
    *,
    action: str,
    entity_id: int,
    user_id: int,
    organization_id: int,
):
    try:
        log_activity(
            db=db,
            action=action,
            entity="invitation",
            entity_id=entity_id,
            user_id=user_id,
            organization_id=organization_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def create_invitation(
    db: Session,
    invitation: InvitationCreate,
    organization_id: int,
    actor_user_id: int,
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
    db.flush()
    _commit_with_audit(
        db,
        action="created",
        entity_id=db_invitation.id,
        user_id=actor_user_id,
        organization_id=organization_id,
    )
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
    actor_user_id: int,
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

    _commit_with_audit(
        db,
        action="revoked",
        entity_id=invitation.id,
        user_id=actor_user_id,
        organization_id=invitation.organization_id,
    )
    db.refresh(invitation)

    return invitation


def resend_invitation(
    db: Session,
    invitation: Invitation,
    actor_user_id: int,
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

    _commit_with_audit(
        db,
        action="resent",
        entity_id=invitation.id,
        user_id=actor_user_id,
        organization_id=invitation.organization_id,
    )
    db.refresh(invitation)

    return invitation


def create_user_from_invitation(
    db: Session,
    invitation: Invitation,
    name: str,
    password: str,
):
    email = normalize_email(invitation.email)

    organization = invitation.organization

    if (
        organization is None
        or not organization.is_active
    ):
        raise ValueError(
            "Organization is inactive"
        )

    existing_user = get_user_by_email(
        db,
        email,
    )

    if existing_user:
        raise ValueError(
            "A user with this email already exists."
        )

    user = User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        role=invitation.role,
        organization_id=invitation.organization_id,
        is_active=True,
    )

    db.add(user)
    db.flush()

    invitation.status = "accepted"

    _commit_with_audit(
        db,
        action="accepted",
        entity_id=invitation.id,
        user_id=user.id,
        organization_id=invitation.organization_id,
    )
    db.refresh(user)

    return user