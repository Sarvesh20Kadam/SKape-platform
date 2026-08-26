from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role
from app.crud.device import get_device_by_id
from app.crud.telemetry import (
    create_telemetry,
    get_latest_telemetry,
    get_device_telemetry,
)
from app.schemas.telemetry import (
    TelemetryCreate,
    TelemetryResponse,
)


router = APIRouter(
    prefix="/devices",
    tags=["Device Telemetry"],
)


@router.post(
    "/{device_id}/telemetry",
    response_model=TelemetryResponse,
)
def create_device_telemetry(
    device_id: int,
    telemetry: TelemetryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    device = get_device_by_id(
        db=db,
        device_id=device_id,
        organization_id=current_user.organization_id,
    )

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    return create_telemetry(
        db=db,
        device=device,
        telemetry=telemetry,
    )


@router.get(
    "/{device_id}/telemetry/latest",
    response_model=TelemetryResponse,
)
def latest_device_telemetry(
    device_id: int,
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
    device = get_device_by_id(
        db=db,
        device_id=device_id,
        organization_id=current_user.organization_id,
    )

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    telemetry = get_latest_telemetry(
        db=db,
        device=device,
    )

    if telemetry is None:
        raise HTTPException(
            status_code=404,
            detail="No telemetry available",
        )

    return telemetry


@router.get(
    "/{device_id}/telemetry",
    response_model=List[TelemetryResponse],
)
def device_telemetry_history(
    device_id: int,
    limit: int = 50,
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
    if limit < 1:
        raise HTTPException(
            status_code=400,
            detail="Limit must be greater than 0",
        )

    if limit > 500:
        limit = 500

    device = get_device_by_id(
        db=db,
        device_id=device_id,
        organization_id=current_user.organization_id,
    )

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    return get_device_telemetry(
        db=db,
        device=device,
        limit=limit,
    )