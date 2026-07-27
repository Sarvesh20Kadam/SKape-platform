from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate
from app.security import (
    hash_password,
    verify_password,
)


def create_user(db: Session, user: UserCreate):
    db_user = User(
        name=user.name,
        email=user.email,
        hashed_password=hash_password(user.password),
        role="employee",
        is_active=True,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


def get_user_by_email(
    db: Session,
    email: str
):
    return (
        db.query(User)
        .filter(User.email == email)
        .first()
    )


def authenticate_user(
    db: Session,
    email: str,
    password: str
):
    print("Login email:", email)

    user = get_user_by_email(db, email)

    print("User found:", user)

    if not user:
        return None

    print("Stored hash:", user.hashed_password)

    result = verify_password(
        password,
        user.hashed_password
    )

    print("Password valid:", result)

    if not result:
        return None

    return user