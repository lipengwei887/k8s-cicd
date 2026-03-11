from sqlalchemy import Column, Integer, String, Enum, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class PermissionRole(str, enum.Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cluster_id = Column(Integer, ForeignKey("clusters.id", ondelete="CASCADE"), nullable=True)
    namespace_id = Column(Integer, ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=True)
    role = Column(Enum(PermissionRole), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="permissions")
    cluster = relationship("Cluster")
    namespace = relationship("Namespace")
