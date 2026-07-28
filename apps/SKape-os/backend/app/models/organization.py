from sqlalchemy import Boolean, Column, Integer, String

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    slug = Column(String, unique=True, nullable=False)

    email = Column(String, unique=True)

    phone = Column(String)

    website = Column(String)

    logo = Column(String)

    industry = Column(String)

    address = Column(String)

    is_active = Column(Boolean, default=True)