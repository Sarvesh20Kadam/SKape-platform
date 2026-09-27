from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.alert_task import create_maintenance_task_from_alert
from app.schemas.task import TaskResponse

from app.database import get_db
from app.permissions import require_role
from app.crud.alert import (
    get_alerts,
    get_alert_by_id,
    resolve_alert,
)
from app.schemas.alert import AlertResponse


router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"],
)


@router.get(
    "/",
    response_model=List[AlertResponse],
)
def get_all_alerts(
    skip: int = 0,
    limit: int = 50,
    unresolved_only: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
            "employee",
        )
    ),
):
    if skip < 0:
        raise HTTPException(
            status_code=400,
            detail="Skip must be greater than or equal to 0",
        )

    if limit < 1:
        raise HTTPException(
            status_code=400,
            detail="Limit must be greater than 0",
        )

    if limit > 500:
        limit = 500

    return get_alerts(
        db=db,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
        unresolved_only=unresolved_only,
    )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
)
def get_one_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
            "employee",
        )
    ),
):
    alert = get_alert_by_id(
        db=db,
        alert_id=alert_id,
        organization_id=current_user.organization_id,
    )

    if alert is None:
        raise HTTPException(
            status_code=404,
            detail="Alert not found",
        )

    return alert


@router.patch(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
)
def resolve_one_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    alert = get_alert_by_id(
        db=db,
        alert_id=alert_id,
        organization_id=current_user.organization_id,
    )

    if alert is None:
        raise HTTPException(
            status_code=404,
            detail="Alert not found",
        )

    return resolve_alert(
        db=db,
        alert=alert,
    )


# ============================================================
# HUMAN → CREATE MAINTENANCE TASK FROM ALERT
# ============================================================

@router.post(
    "/{alert_id}/maintenance-task",
    response_model=TaskResponse,
)
def create_alert_maintenance_task(
    alert_id: int,
    project_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    alert = get_alert_by_id(
        db=db,
        alert_id=alert_id,
        organization_id=current_user.organization_id,
    )

    if alert is None:
        raise HTTPException(
            status_code=404,
            detail="Alert not found",
        )

    try:
        task = create_maintenance_task_from_alert(
            db=db,
            alert=alert,
            project_id=project_id,
        )

        db.commit()
        db.refresh(task)

        return task

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
