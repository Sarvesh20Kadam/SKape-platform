from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserLogin,
    Token,
)

from app.crud.user import (
    create_user,
    get_user_by_email,
    authenticate_user,
)

from app.security import create_access_token

router = APIRouter()


@router.post(
    "/",
    response_model=UserResponse
)
def register(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    existing = get_user_by_email(
        db,
        user.email
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    return create_user(
        db,
        user
    )

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    authenticated_user = authenticate_user(
        db,
        form_data.username,
        form_data.password
    )

    if authenticated_user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    token = create_access_token(
    {
        "sub": authenticated_user.email,
        "role": authenticated_user.role
    }
)

    return {
        "access_token": token,
        "token_type": "bearer",
    }