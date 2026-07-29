from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import verify_token
from app.crud.user import get_user_by_email

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/users/login"
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    user = get_user_by_email(
        db,
        payload["sub"]
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user