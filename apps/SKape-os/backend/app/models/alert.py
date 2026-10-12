from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index(
            "uq_alerts_unresolved_device_offline",
            "device_id",
            unique=True,
            sqlite_where=text(
                "alert_type = 'device_offline' AND NOT is_resolved"
            ),
            postgresql_where=text(
                "alert_type = 'device_offline' AND NOT is_resolved"
            ),
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    device_id = Column(
        Integer,
        ForeignKey("devices.id"),
        nullable=False,
        index=True,
    )

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    severity = Column(
        String,
        nullable=False,
    )

    alert_type = Column(
        String,
        nullable=False,
    )

    title = Column(
        String,
        nullable=False,
    )

    message = Column(
        Text,
        nullable=False,
    )

    is_resolved = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    device = relationship(
        "Device",
        back_populates="alerts",
    )

    organization = relationship(
        "Organization",
        back_populates="alerts",
    )


    tasks = relationship(
        "Task",
        back_populates="alert",
    )
