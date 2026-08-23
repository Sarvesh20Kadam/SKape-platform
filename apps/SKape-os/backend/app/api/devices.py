from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role
from app.exceptions import NotFoundException

from app.crud.device import (
    create_device as db_create_device,
    get_devices as db_get_devices,
    get_device_by_id as db_get_device_by_id,
    update_device as db_update_device,
    delete_device as db_delete_device,
)

from app.schemas.device import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
)


router = APIRouter(
    prefix="/devices",
    tags=["Devices"],
)


@router.post(
    "/",
    response_model=DeviceResponse,
)
def create(
    device: DeviceCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    try:
        return db_create_device(
            db=db,
            device=device,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get(
    "/",
    response_model=List[DeviceResponse],
)
def get_all(
    skip: int = 0,
    limit: int = 10,
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
    return db_get_devices(
        db=db,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{device_id}",
    response_model=DeviceResponse,
)
def get_one(
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
    device = db_get_device_by_id(
        db,
        device_id,
        current_user.organization_id,
    )

    if device is None:
        raise NotFoundException("Device")

    return device


@router.put(
    "/{device_id}",
    response_model=DeviceResponse,
)
def update(
    device_id: int,
    device: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    updated = db_update_device(
        db=db,
        device_id=device_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        updated_device=device,
    )

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    return updated


@router.delete(
    "/{device_id}",
    response_model=DeviceResponse,
)
def delete(
    device_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    deleted = db_delete_device(
        db=db,
        device_id=device_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )

    if deleted is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    return deleted