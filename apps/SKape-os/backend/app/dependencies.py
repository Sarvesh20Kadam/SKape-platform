from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import verify_token
from app.crud.user import get_user_by_email


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/users/login"
)


def _load_authenticated_user(
    token: str,
    db: Session,
    *,
    allow_inactive_organization: bool,
):
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = payload.get("sub")

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_email(
        db,
        subject,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    if user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an organization",
        )

    # --------------------------------------------------------
    # Organization lifecycle security
    # --------------------------------------------------------

    organization = user.organization

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization not found",
        )

    if (
        not organization.is_active
        and not allow_inactive_organization
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is inactive",
        )

    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return _load_authenticated_user(
        token,
        db,
        allow_inactive_organization=False,
    )


def get_owner_for_organization_recovery(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    Authenticate the owner of an organization that may be inactive.

    This dependency is only for reactivation. It does not grant
    access to other protected routes.
    """

    user = _load_authenticated_user(
        token,
        db,
        allow_inactive_organization=True,
    )

    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You don't have permission to "
                "perform this action."
            ),
        )

    return user