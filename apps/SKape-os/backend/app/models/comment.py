from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)

    content = Column(String, nullable=False)

    task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    task = relationship(
        "Task",
        back_populates="comments"
    )

    user = relationship(
        "User",
        back_populates="comments"
    )

    organization = relationship(
        "Organization",
        back_populates="comments"
    )