from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional
import json
import asyncio

from app.database import get_db
from app.models.release import ReleaseRecord, ReleaseStatus
from app.models.service import Service
from app.schemas.release import (
    ReleaseCreate, ReleaseResponse, ReleaseListResponse, 
    ReleaseApprove, ReleaseProgress
)
from app.api.v1.auth import get_current_active_user
from app.models.user import User
from app.services.release_service import ReleaseService

router = APIRouter()

# WebSocket 连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, release_id: int):
        await websocket.accept()
        if release_id not in self.active_connections:
            self.active_connections[release_id] = []
        self.active_connections[release_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, release_id: int):
        if release_id in self.active_connections:
            self.active_connections[release_id].remove(websocket)
    
    async def broadcast(self, release_id: int, message: dict):
        if release_id in self.active_connections:
            for connection in self.active_connections[release_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = ConnectionManager()


@router.get("", response_model=ReleaseListResponse)
async def list_releases(
    skip: int = 0,
    limit: int = 100,
    service_id: Optional[int] = None,
    status: Optional[ReleaseStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取发布记录列表"""
    query = select(ReleaseRecord)
    
    if service_id:
        query = query.where(ReleaseRecord.service_id == service_id)
    if status:
        query = query.where(ReleaseRecord.status == status)
    
    query = query.order_by(desc(ReleaseRecord.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    releases = result.scalars().all()
    
    # 获取总数
    count_query = select(func.count(ReleaseRecord.id))
    if service_id:
        count_query = count_query.where(ReleaseRecord.service_id == service_id)
    if status:
        count_query = count_query.where(ReleaseRecord.status == status)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return {"items": releases, "total": total}


@router.post("", response_model=ReleaseResponse, status_code=status.HTTP_201_CREATED)
async def create_release(
    release: ReleaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建发布单"""
    release_service = ReleaseService(db)
    
    db_release = await release_service.create_release(
        service_id=release.service_id,
        operator_id=current_user.id,
        image_tag=release.image_tag,
        version=release.version,
        require_approval=release.require_approval
    )
    
    return db_release


@router.get("/{release_id}", response_model=ReleaseResponse)
async def get_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取发布详情"""
    result = await db.execute(select(ReleaseRecord).where(ReleaseRecord.id == release_id))
    release = result.scalar_one_or_none()
    
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    
    return release


@router.post("/{release_id}/execute")
async def execute_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """执行发布"""
    release_service = ReleaseService(db)
    
    try:
        result = await release_service.execute_release(release_id, current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{release_id}/rollback")
async def rollback_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """回滚发布"""
    release_service = ReleaseService(db)
    
    try:
        result = await release_service.rollback_release(release_id, current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{release_id}/approve")
async def approve_release(
    release_id: int,
    approve_data: ReleaseApprove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """审批发布单"""
    result = await db.execute(select(ReleaseRecord).where(ReleaseRecord.id == release_id))
    release = result.scalar_one_or_none()
    
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    
    if release.status != ReleaseStatus.APPROVING:
        raise HTTPException(status_code=400, detail="Release is not waiting for approval")
    
    if approve_data.approved:
        release.status = ReleaseStatus.PENDING
        release.approved_by = current_user.id
        release.approved_at = datetime.utcnow()
    else:
        release.status = ReleaseStatus.FAILED
        release.message = f"Rejected: {approve_data.comment or 'No comment'}"
    
    await db.commit()
    await db.refresh(release)
    
    return release


@router.websocket("/{release_id}/progress")
async def websocket_endpoint(
    websocket: WebSocket,
    release_id: int,
    db: AsyncSession = Depends(get_db)
):
    """WebSocket 实时推送发布进度"""
    await manager.connect(websocket, release_id)
    
    try:
        while True:
            # 获取最新发布状态
            result = await db.execute(
                select(ReleaseRecord).where(ReleaseRecord.id == release_id)
            )
            release = result.scalar_one_or_none()
            
            if release and release.pod_status:
                progress = json.loads(release.pod_status)
                await websocket.send_json(progress)
            
            # 每 3 秒推送一次
            await asyncio.sleep(3)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, release_id)
    except Exception as e:
        manager.disconnect(websocket, release_id)


from datetime import datetime
