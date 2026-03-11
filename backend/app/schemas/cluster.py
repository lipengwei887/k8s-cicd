from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ClusterBase(BaseModel):
    name: str
    display_name: Optional[str] = None
    api_server: str
    description: Optional[str] = None


class ClusterCreate(ClusterBase):
    kubeconfig: Optional[str] = None
    sa_token: Optional[str] = None
    ca_cert: Optional[str] = None


class ClusterUpdate(BaseModel):
    display_name: Optional[str] = None
    api_server: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None


class ClusterResponse(ClusterBase):
    id: int
    status: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ClusterListResponse(BaseModel):
    items: List[ClusterResponse]
    total: int
