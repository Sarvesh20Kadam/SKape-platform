from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role
from app.crud.device import get_device_by_id
from app.crud.telemetry import get_latest_telemetry
from app.schemas.device_health import DeviceHealthResponse
from app.services.device_health import calculate_device_health


router = APIRouter(
    prefix="/devices",
    tags=["Device Health"],
)


@router.get(
    "/{device_id}/health",
    response_model=DeviceHealthResponse,
)
def get_device_health(
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

    latest_telemetry = get_latest_telemetry(
        db=db,
        device=device,
    )

    return calculate_device_health(
        device=device,
        latest_telemetry=latest_telemetry,
    )