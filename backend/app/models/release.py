from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Text, JSON, DateTime, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class ReleaseStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVING = "approving"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ReleaseStrategy(str, enum.Enum):
    ROLLING = "rolling"
    RECREATE = "recreate"
    CANARY = "canary"


class ReleaseRecord(Base):
    __tablename__ = "release_records"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    version = Column(String(64), nullable=False)
    image_tag = Column(String(128), nullable=False)
    image_full_path = Column(String(255))
    previous_image = Column(String(255))
    status = Column(Enum(ReleaseStatus), default=ReleaseStatus.PENDING)
    strategy = Column(Enum(ReleaseStrategy), default=ReleaseStrategy.ROLLING)
    message = Column(Text)
    pod_status = Column(JSON)
    rollback_to = Column(Integer, ForeignKey("release_records.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 关系
    service = relationship("Service", back_populates="releases")
    operator = relationship("User", foreign_keys=[operator_id], back_populates="releases")
    approver = relationship("User", foreign_keys=[approved_by])
