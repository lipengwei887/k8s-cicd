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
    image_tag = Column(String(128), nullable=False)
    image_full_path = Column(String(255))
    previous_image = Column(String(255))
    status = Column(Enum(ReleaseStatus), default=ReleaseStatus.PENDING)
    strategy = Column(Enum(ReleaseStrategy), default=ReleaseStrategy.ROLLING)
    message = Column(Text)
    pod_status = Column(JSON)
    logs = Column(Text)  # Pod 日志
    rollback_to = Column(Integer, ForeignKey("release_records.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 发布时效相关字段
    # validity_period: 时效时长（小时），0 表示不限制，1-168 表示 1 小时到 7 天
    validity_period = Column(Integer, default=0, nullable=False)
    # validity_start_at: 时效开始时间（审批通过时设置）
    validity_start_at = Column(DateTime, nullable=True)
    # validity_end_at: 时效结束时间
    validity_end_at = Column(DateTime, nullable=True)
    # parent_release_id: 父发布单 ID，用于关联同一审批的多次执行
    parent_release_id = Column(Integer, ForeignKey("release_records.id"), nullable=True)
    # is_repeated: 是否为重复执行（时效内再次发布）
    is_repeated = Column(Integer, default=0, nullable=False)
    
    # 关系
    service = relationship("Service", back_populates="releases")
    operator = relationship("User", foreign_keys=[operator_id], back_populates="releases")
    approver = relationship("User", foreign_keys=[approved_by])
    parent_release = relationship("ReleaseRecord", remote_side=[id], foreign_keys=[parent_release_id])
    
    def is_validity_expired(self) -> bool:
        """检查时效是否过期"""
        if self.validity_period == 0 or not self.validity_end_at:
            return True
        from datetime import datetime, timezone
        # 使用 UTC 时间进行比较
        return datetime.now(timezone.utc) > self.validity_end_at.replace(tzinfo=timezone.utc)
    
    def can_execute_without_approval(self) -> bool:
        """检查是否可以在时效内免审批执行"""
        if self.validity_period == 0 or not self.validity_end_at:
            return False
        from datetime import datetime, timezone
        # 使用 UTC 时间进行比较
        return datetime.now(timezone.utc) <= self.validity_end_at.replace(tzinfo=timezone.utc)
