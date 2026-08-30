from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    device_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    name = Column(
        String,
        nullable=False,
    )

    device_type = Column(
        String,
        nullable=False,
    )

    status = Column(
        String,
        default="offline",
        nullable=False,
    )

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
    )

    asset_id = Column(
        Integer,
        ForeignKey("assets.id"),
        nullable=True,
    )

    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization = relationship(
        "Organization",
        back_populates="devices",
    )

    asset = relationship(
        "Asset",
        back_populates="devices",
    )

    telemetry = relationship(
        "DeviceTelemetry",
        back_populates="device",
        cascade="all, delete-orphan",
    )

    alerts = relationship(
    "Alert",
    back_populates="device",
    cascade="all, delete-orphan",
)