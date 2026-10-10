import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.permissions import require_role

from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserRoleUpdate,
    Token,
)

from app.crud.user import (
    create_user,
    authenticate_user,
    update_user_role,
)

from app.security import (
    create_access_token,
    validate_password_length,
    wait_for_login_failure,
)

REGISTRATION_CONFLICT = (
    "Registration could not be completed."
)


router = APIRouter()


@router.post(
    "/",
    response_model=UserResponse,
)
def register(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    try:
        validate_password_length(user.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    try:
        return create_user(
            db,
            user,
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=REGISTRATION_CONFLICT,
        )


@router.post(
    "/login",
    response_model=Token,
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    started = time.monotonic()
    authenticated_user = authenticate_user(
        db,
        form_data.username,
        form_data.password,
    )

    if authenticated_user is None:
        wait_for_login_failure(started)
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    if not authenticated_user.is_active:
        wait_for_login_failure(started)
        raise HTTPException(
            status_code=403,
            detail="User account is inactive",
        )

    organization = authenticated_user.organization

    if organization is None:
        wait_for_login_failure(started)
        raise HTTPException(
            status_code=403,
            detail="Organization not found",
        )

    if not organization.is_active:
        wait_for_login_failure(started)
        raise HTTPException(
            status_code=403,
            detail="Organization is inactive",
        )

    token = create_access_token(
        {
            "sub": authenticated_user.email,
            "role": authenticated_user.role,
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user=Depends(get_current_user),
):
    return current_user



@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
)
def update_role(
    user_id: int,
    request: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("owner", "admin"),
    ),
):
    user = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.organization_id
            == current_user.organization_id,
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot change your own role.",
        )

    if user.role == "owner":
        raise HTTPException(
            status_code=403,
            detail="The organization owner cannot be modified.",
        )

    if (
        request.role == "admin"
        and current_user.role != "owner"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "You don't have permission to "
                "perform this action."
            ),
        )

    if (
        current_user.role == "admin"
        and user.role == "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail="Admins cannot modify another admin.",
        )

    try:
        return update_user_role(
            db=db,
            user=user,
            role=request.role,
            actor_user_id=current_user.id,
)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )