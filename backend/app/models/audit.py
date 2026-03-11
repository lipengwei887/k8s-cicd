from sqlalchemy import Column, Integer, String, JSON, DateTime, TIMESTAMP
from sqlalchemy.sql import func
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(64))
    action = Column(String(32), nullable=False, index=True)
    resource_type = Column(String(32), nullable=False, index=True)
    resource_id = Column(Integer, nullable=True)
    resource_name = Column(String(128))
    detail = Column(JSON)
    ip_addr = Column(String(64))
    user_agent = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
