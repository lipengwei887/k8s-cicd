from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Cluster(Base):
    __tablename__ = "clusters"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(128))
    api_server = Column(String(255), nullable=False)
    kubeconfig_encrypted = Column(Text)
    sa_token_encrypted = Column(Text)
    ca_cert = Column(Text)
    status = Column(Integer, default=1)  # 0-禁用 1-启用
    description = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # 关系
    namespaces = relationship("Namespace", back_populates="cluster", cascade="all, delete-orphan")
