from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role

from app.crud.activity import get_activities
from app.schemas.activity import ActivityResponse


router = APIRouter(
    prefix="/activities",
    tags=["Activities"],
)


@router.get(
    "/",
    response_model=List[ActivityResponse],
)
def get_all(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    return get_activities(
        db=db,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
    )