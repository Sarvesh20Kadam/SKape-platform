from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
)

from sqlalchemy.orm import relationship

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    description = Column(String)

    status = Column(String, default="active")

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False
    )

    organization = relationship(
        "Organization",
        back_populates="projects"
    )