from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role
from app.exceptions import NotFoundException
from app.device_auth import get_authenticated_device

from app.crud.device import (
    create_device as db_create_device,
    get_devices as db_get_devices,
    get_device_by_id as db_get_device_by_id,
    update_device as db_update_device,
    delete_device as db_delete_device,
    heartbeat_device as db_heartbeat_device,
)

from app.crud.device_credential import (
    create_device_credential,
    revoke_device_credential as db_revoke_device_credential,
)

from app.schemas.device import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
)

from app.schemas.device_credential import (
    DeviceCredentialProvisionResponse,
    DeviceCredentialResponse,
)


router = APIRouter(
    prefix="/devices",
    tags=["Devices"],
)


# ============================================================
# HUMAN → CREATE DEVICE
# ============================================================

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


# ============================================================
# HUMAN → LIST DEVICES
# ============================================================

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


# ============================================================
# DEVICE → HEARTBEAT
# ============================================================

@router.post(
    "/heartbeat",
    response_model=DeviceResponse,
)
def heartbeat(
    db: Session = Depends(get_db),
    authenticated_device=Depends(get_authenticated_device),
):
    """
    Receive a heartbeat from an authenticated physical device.

    Authentication:
        X-Device-ID
        X-Device-Secret
    """

    device = db_heartbeat_device(
        db=db,
        device_id=authenticated_device.device_id,
    )

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    return device


# ============================================================
# HUMAN → PROVISION DEVICE CREDENTIAL
# ============================================================

@router.post(
    "/{device_id}/credentials",
    response_model=DeviceCredentialProvisionResponse,
)
def provision_device_credential(
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
    device = db_get_device_by_id(
        db=db,
        device_id=device_id,
        organization_id=current_user.organization_id,
    )

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    try:
        credential, raw_secret = create_device_credential(
            db=db,
            device=device,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e),
        )

    return {
        "credential": credential,
        "device_secret": raw_secret,
    }


# ============================================================
# HUMAN → REVOKE DEVICE CREDENTIAL
# ============================================================

@router.post(
    "/{device_id}/credentials/revoke",
    response_model=DeviceCredentialResponse,
)
def revoke_device_credential(
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
    device = db_get_device_by_id(
        db=db,
        device_id=device_id,
        organization_id=current_user.organization_id,
    )

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    credential = db_revoke_device_credential(
        db=db,
        device=device,
    )

    if credential is None:
        raise HTTPException(
            status_code=404,
            detail="No active credential found",
        )

    return credential


# ============================================================
# HUMAN → GET DEVICE
# ============================================================

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


# ============================================================
# HUMAN → UPDATE DEVICE
# ============================================================

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


# ============================================================
# HUMAN → DELETE DEVICE
# ============================================================

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