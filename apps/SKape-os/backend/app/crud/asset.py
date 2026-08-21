from sqlalchemy.orm import Session

from app.crud.activity import log_activity
from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetUpdate


def create_asset(
    db: Session,
    asset: AssetCreate,
    organization_id: int,
    user_id: int,
):
    db_asset = Asset(
        name=asset.name,
        asset_type=asset.asset_type,
        description=asset.description,
        location=asset.location,
        status=asset.status,
        assigned_to=asset.assigned_to,
        organization_id=organization_id,
        is_active=True,
    )

    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)

    log_activity(
        db=db,
        action="created",
        entity="asset",
        entity_id=db_asset.id,
        user_id=user_id,
        organization_id=organization_id,
    )

    return db_asset


def get_assets(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10,
):
    return (
        db.query(Asset)
        .filter(
            Asset.organization_id == organization_id
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_asset_by_id(
    db: Session,
    asset_id: int,
    organization_id: int,
):
    return (
        db.query(Asset)
        .filter(
            Asset.id == asset_id,
            Asset.organization_id == organization_id,
        )
        .first()
    )


def update_asset(
    db: Session,
    asset_id: int,
    organization_id: int,
    user_id: int,
    updated_asset: AssetUpdate,
):
    asset = get_asset_by_id(
        db,
        asset_id,
        organization_id,
    )

    if asset is None:
        return None

    update_data = updated_asset.model_dump(
        exclude_unset=True,
    )

    for key, value in update_data.items():
        setattr(asset, key, value)

    db.commit()
    db.refresh(asset)

    log_activity(
        db=db,
        action="updated",
        entity="asset",
        entity_id=asset.id,
        user_id=user_id,
        organization_id=organization_id,
    )

    return asset


def delete_asset(
    db: Session,
    asset_id: int,
    organization_id: int,
    user_id: int,
):
    asset = get_asset_by_id(
        db,
        asset_id,
        organization_id,
    )

    if asset is None:
        return None

    deleted_asset_id = asset.id

    db.delete(asset)
    db.commit()

    log_activity(
        db=db,
        action="deleted",
        entity="asset",
        entity_id=deleted_asset_id,
        user_id=user_id,
        organization_id=organization_id,
    )

    return asset