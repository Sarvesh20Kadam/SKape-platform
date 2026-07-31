from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
)

from sqlalchemy.orm import relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    slug = Column(String, unique=True, index=True, nullable=False)

    email = Column(String, unique=True, nullable=True)

    phone = Column(String, nullable=True)

    website = Column(String, nullable=True)

    logo = Column(String, nullable=True)

    industry = Column(String, nullable=True)

    address = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)

    users = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

    projects = relationship(
        "Project",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

    invitations = relationship(
        "Invitation",
        back_populates="organization",
        cascade="all, delete-orphan"
    )