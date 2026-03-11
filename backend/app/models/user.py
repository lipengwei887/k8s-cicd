from sqlalchemy import Column, Integer, String, Enum, DateTime, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    APPROVER = "approver"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(128), unique=True, nullable=False)
    real_name = Column(String(64))
    role = Column(Enum(UserRole), default=UserRole.DEVELOPER)
    status = Column(Integer, default=1)  # 0-禁用 1-启用
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # 关系
    permissions = relationship("Permission", back_populates="user", cascade="all, delete-orphan")
    releases = relationship("ReleaseRecord", foreign_keys="ReleaseRecord.operator_id", back_populates="operator")
