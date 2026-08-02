from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role

from app.crud.activity import get_activities
from app.schemas.activity import ActivityResponse

router = APIRouter(
    prefix="/activities",
    tags=["Activities"]
)


@router.get(
    "/",
    response_model=List[ActivityResponse]
)
def get_all(
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
            "employee"
        )
    )
):
    return get_activities(
        db,
        current_user.organization_id
    )