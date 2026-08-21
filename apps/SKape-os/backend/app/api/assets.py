from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role
from app.exceptions import NotFoundException

from app.crud.asset import (
    create_asset as db_create_asset,
    get_assets as db_get_assets,
    get_asset_by_id as db_get_asset_by_id,
    update_asset as db_update_asset,
    delete_asset as db_delete_asset,
)

from app.schemas.asset import (
    AssetCreate,
    AssetUpdate,
    AssetResponse,
)


router = APIRouter(
    prefix="/assets",
    tags=["Assets"],
)


@router.post(
    "/",
    response_model=AssetResponse,
)
def create(
    asset: AssetCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    return db_create_asset(
        db=db,
        asset=asset,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )


@router.get(
    "/",
    response_model=List[AssetResponse],
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
    return db_get_assets(
        db=db,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
)
def get_one(
    asset_id: int,
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
    asset = db_get_asset_by_id(
        db,
        asset_id,
        current_user.organization_id,
    )

    if asset is None:
        raise NotFoundException("Asset")

    return asset


@router.put(
    "/{asset_id}",
    response_model=AssetResponse,
)
def update(
    asset_id: int,
    asset: AssetUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    updated = db_update_asset(
        db=db,
        asset_id=asset_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        updated_asset=asset,
    )

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found",
        )

    return updated


@router.delete(
    "/{asset_id}",
    response_model=AssetResponse,
)
def delete(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    deleted = db_delete_asset(
        db=db,
        asset_id=asset_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )

    if deleted is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found",
        )

    return deleted