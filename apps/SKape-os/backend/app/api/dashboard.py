from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role

from app.crud.dashboard import get_dashboard
from app.schemas.dashboard import DashboardResponse

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get(
    "/",
    response_model=DashboardResponse
)
def dashboard(
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
    return get_dashboard(
        db,
        current_user.organization_id
    )