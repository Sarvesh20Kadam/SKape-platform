from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud.activity import log_activity
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
            Alert.organization_id == organization_id
        )
    )

    if unresolved_only:
        query = query.filter(
            Alert.is_resolved.is_(False)
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


def get_active_device_alert(
    db: Session,
    device_id: int,
    organization_id: int,
    alert_type: str,
):
    return (
        db.query(Alert)
        .filter(
            Alert.device_id == device_id,
            Alert.organization_id == organization_id,
            Alert.alert_type == alert_type,
            Alert.is_resolved.is_(False),
        )
        .order_by(Alert.created_at.desc())
        .first()
    )


def create_alert(
    db: Session,
    *,
    device_id: int,
    organization_id: int,
    severity: str,
    alert_type: str,
    title: str,
    message: str,
):
    """
    Create an alert only when an active alert of the same
    type does not already exist for the device.

    The pre-check avoids an insert on the common path. Concurrent
    workers are still limited by the unique index on one unresolved
    device_offline alert per device. A lost insert keeps the caller's
    other pending changes and returns the winning alert.
    """

    existing_alert = get_active_device_alert(
        db=db,
        device_id=device_id,
        organization_id=organization_id,
        alert_type=alert_type,
    )

    if existing_alert is not None:
        return existing_alert, False

    alert = Alert(
        device_id=device_id,
        organization_id=organization_id,
        severity=severity,
        alert_type=alert_type,
        title=title,
        message=message,
        is_resolved=False,
    )

    try:
        with db.begin_nested():
            db.add(alert)
            db.flush([alert])
    except IntegrityError:
        existing_alert = get_active_device_alert(
            db=db,
            device_id=device_id,
            organization_id=organization_id,
            alert_type=alert_type,
        )
        if existing_alert is None:
            raise
        return existing_alert, False

    return alert, True


def resolve_alert(
    db: Session,
    alert: Alert,
    user_id: int,
):
    if alert.is_resolved:
        return alert

    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)

    try:
        log_activity(
            db=db,
            action="resolved",
            entity="alert",
            entity_id=alert.id,
            user_id=user_id,
            organization_id=alert.organization_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(alert)

    return alert