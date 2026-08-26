from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class DeviceTelemetry(Base):
    __tablename__ = "device_telemetry"

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

    temperature = Column(
        Float,
        nullable=True,
    )

    sensor_1 = Column(
        Float,
        nullable=True,
    )

    sensor_2 = Column(
        Float,
        nullable=True,
    )

    sensor_3 = Column(
        Float,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    device = relationship(
        "Device",
        back_populates="telemetry",
    )