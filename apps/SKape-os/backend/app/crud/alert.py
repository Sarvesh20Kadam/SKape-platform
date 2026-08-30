from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.alert import Alert


def get_alerts(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 50,
    unresolved_only: bool = False,
):
    query = (
        db.query(Alert)
        .filter(
            Alert.organization_id == organization_id,
        )
    )

    if unresolved_only:
        query = query.filter(
            Alert.is_resolved.is_(False),
        )

    return (
        query
        .order_by(Alert.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_alert_by_id(
    db: Session,
    alert_id: int,
    organization_id: int,
):
    return (
        db.query(Alert)
        .filter(
            Alert.id == alert_id,
            Alert.organization_id == organization_id,
        )
        .first()
    )


def resolve_alert(
    db: Session,
    alert: Alert,
):
    if alert.is_resolved:
        return alert

    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)

    return alert