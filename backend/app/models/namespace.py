from sqlalchemy import Column, Integer, String, Enum, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class EnvType(str, enum.Enum):
    DEV = "dev"
    TEST = "test"
    STAGING = "staging"
    PROD = "prod"


class Namespace(Base):
    __tablename__ = "namespaces"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cluster_id = Column(Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(64), nullable=False)
    display_name = Column(String(128))
    env_type = Column(Enum(EnvType), nullable=False)
    status = Column(Integer, default=1)
    description = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # 关系
    cluster = relationship("Cluster", back_populates="namespaces")
    services = relationship("Service", back_populates="namespace", cascade="all, delete-orphan")
    role_groups = relationship("RoleGroupNamespace", back_populates="namespace")
