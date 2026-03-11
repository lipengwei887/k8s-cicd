from sqlalchemy import Column, Integer, String, Enum, ForeignKey, JSON, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class ServiceType(str, enum.Enum):
    DEPLOYMENT = "deployment"
    STATEFULSET = "statefulset"


class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    namespace_id = Column(Integer, ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(64), nullable=False)
    display_name = Column(String(128))
    type = Column(Enum(ServiceType), default=ServiceType.DEPLOYMENT)
    deploy_name = Column(String(128), nullable=False)
    container_name = Column(String(128))
    harbor_project = Column(String(64))
    harbor_repo = Column(String(128))
    current_image = Column(String(255))  # 当前运行的镜像地址
    port = Column(Integer)
    replicas = Column(Integer, default=1)
    resource_limits = Column(JSON)
    health_check_path = Column(String(128), default="/health")
    status = Column(Integer, default=1)
    description = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # 关系
    namespace = relationship("Namespace", back_populates="services")
    releases = relationship("ReleaseRecord", back_populates="service")
