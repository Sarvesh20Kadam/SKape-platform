from sqlalchemy.orm import Session

from app.models.activity import Activity


def log_activity(
    db: Session,
    action: str,
    entity: str,
    entity_id: int,
    user_id: int,
    organization_id: int,
):
    """
    Create an activity/audit record.

    Transaction ownership remains with the caller.
    This function only adds and flushes the record.
    """

    activity = Activity(
        action=action,
        entity=entity,
        entity_id=entity_id,
        user_id=user_id,
        organization_id=organization_id,
    )

    db.add(activity)
    db.flush()

    return activity


def get_activities(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10,
):
    """
    Return activities belonging to the current organization,
    newest first.
    """

    return (
        db.query(Activity)
        .filter(
            Activity.organization_id == organization_id
        )
        .order_by(Activity.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )