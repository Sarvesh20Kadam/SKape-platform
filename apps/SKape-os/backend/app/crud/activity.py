from sqlalchemy.orm import Session

from app.models.activity import Activity


def log_activity(
    db: Session,
    action: str,
    entity: str,
    entity_id: int,
    user_id: int,
    organization_id: int
):
    activity = Activity(
        action=action,
        entity=entity,
        entity_id=entity_id,
        user_id=user_id,
        organization_id=organization_id,
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)

    return activity


def get_activities(
    db: Session,
    organization_id: int
):
    return (
        db.query(Activity)
        .filter(
            Activity.organization_id == organization_id
        )
        .order_by(Activity.created_at.desc())
        .all()
    )