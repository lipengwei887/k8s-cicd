from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.release import ReleaseStatus, ReleaseStrategy


class ReleaseBase(BaseModel):
    service_id: int
    image_tag: str
    require_approval: Optional[bool] = False
    # 发布时效：0 表示不限制，1-168 表示 1 小时到 7 天
    validity_period: Optional[int] = 0


class ReleaseCreate(ReleaseBase):
    class Config:
        extra = 'ignore'


class ReleaseResponse(BaseModel):
    id: int
    service_id: int
    operator_id: int
    image_tag: str
    image_full_path: Optional[str] = None
    previous_image: Optional[str] = None
    status: ReleaseStatus
    strategy: ReleaseStrategy
    message: Optional[str] = None
    pod_status: Optional[Dict[str, Any]] = None
    rollback_to: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    # 时效相关字段
    validity_period: int = 0
    validity_start_at: Optional[datetime] = None
    validity_end_at: Optional[datetime] = None
    parent_release_id: Optional[int] = None
    is_repeated: int = 0
    # 是否可以在时效内免审批执行
    can_execute_without_approval: Optional[bool] = False
    
    class Config:
        from_attributes = True


class ReleaseExecute(BaseModel):
    pass


class ReleaseApprove(BaseModel):
    approved: bool
    comment: Optional[str] = None


class ReleaseProgress(BaseModel):
    desired: int
    updated: int
    ready: int
    available: int
    unavailable: int
    progress_percent: float
    elapsed_seconds: int
    status: str
    message: Optional[str] = None


class ReleaseListResponse(BaseModel):
    items: List[ReleaseResponse]
    total: int
