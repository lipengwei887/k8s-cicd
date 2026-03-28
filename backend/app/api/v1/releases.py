from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional
import json
import asyncio
import logging
from datetime import datetime, timezone

from app.database import get_db, AsyncSessionLocal
from app.models.release import ReleaseRecord, ReleaseStatus
from app.models.service import Service
from app.schemas.release import (
    ReleaseCreate, ReleaseResponse, ReleaseListResponse, 
    ReleaseApprove, ReleaseProgress
)
from app.api.v1.auth import get_current_active_user
from app.models.user import User
from app.services.release_service import ReleaseService
from app.services.rbac_service import RBACService

logger = logging.getLogger(__name__)

# 全局 task 引用集合，防止 asyncio.create_task 创建的 task 被 GC 回收
_background_tasks: set = set()


async def _run_release_in_background(release_id: int, operator_id: int):
    """后台执行发布任务（已由端点将状态置为 RUNNING）"""
    async with AsyncSessionLocal() as db:
        try:
            release_service = ReleaseService(db)
            await release_service.execute_release(release_id, operator_id)
        except Exception as e:
            logger.error(f"Background release {release_id} failed: {e}")

# 权限码中文映射
PERMISSION_NAMES = {
    "release:create": "创建发布",
    "release:execute": "执行发布",
    "release:rollback": "回滚发布",
    "release:read": "查看发布",
    "release:approve": "审批发布",
    "service:create": "创建服务",
    "service:update": "编辑服务",
    "service:delete": "删除服务",
    "service:read": "查看服务",
    "service:deploy": "部署服务",
    "cluster:create": "创建集群",
    "cluster:update": "编辑集群",
    "cluster:delete": "删除集群",
    "cluster:read": "查看集群",
    "namespace:create": "创建命名空间",
    "namespace:update": "编辑命名空间",
    "namespace:delete": "删除命名空间",
    "namespace:read": "查看命名空间",
    "user:create": "创建用户",
    "user:update": "编辑用户",
    "user:delete": "删除用户",
    "user:read": "查看用户",
    "role:create": "创建角色",
    "role:update": "编辑角色",
    "role:delete": "删除角色",
    "role:read": "查看角色",
}

# 权限检查依赖
def require_permission(permission_code: str):
    async def check_permission(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        rbac_service = RBACService(db)
        has_perm = await rbac_service.check_permission(current_user.id, permission_code)
        if not has_perm:
            perm_name = PERMISSION_NAMES.get(permission_code, permission_code)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"没有权限：{perm_name}"
            )
        return current_user
    return check_permission

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


@router.get("")
async def list_releases(
    skip: int = 0,
    limit: int = 100,
    service_id: Optional[int] = None,
    status: Optional[ReleaseStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取发布记录列表
    - 普通用户：只能看到自己的发布记录
    - 管理员：可以看到全部发布记录
    """
    query = select(ReleaseRecord)
    
    # 权限过滤：非管理员只能看到自己的发布记录
    if not current_user.is_superuser:
        query = query.where(ReleaseRecord.operator_id == current_user.id)
    
    if service_id:
        query = query.where(ReleaseRecord.service_id == service_id)
    if status:
        query = query.where(ReleaseRecord.status == status)
    
    query = query.order_by(desc(ReleaseRecord.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    releases = result.scalars().all()
    
    # 获取总数
    count_query = select(func.count(ReleaseRecord.id))
    # 权限过滤：非管理员只能统计自己的发布记录
    if not current_user.is_superuser:
        count_query = count_query.where(ReleaseRecord.operator_id == current_user.id)
    if service_id:
        count_query = count_query.where(ReleaseRecord.service_id == service_id)
    if status:
        count_query = count_query.where(ReleaseRecord.status == status)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # 手动构建响应数据，处理 can_execute_without_approval 方法
    items = []
    for r in releases:
        item = {
            "id": r.id,
            "service_id": r.service_id,
            "operator_id": r.operator_id,
            "image_tag": r.image_tag,
            "image_full_path": r.image_full_path,
            "previous_image": r.previous_image,
            "status": r.status,
            "strategy": r.strategy,
            "message": r.message,
            "pod_status": r.pod_status,
            "logs": r.logs,
            "rollback_to": r.rollback_to,
            "approved_by": r.approved_by,
            "approved_at": r.approved_at,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "created_at": r.created_at,
            "validity_period": r.validity_period,
            "validity_start_at": r.validity_start_at,
            "validity_end_at": r.validity_end_at,
            "parent_release_id": r.parent_release_id,
            "is_repeated": r.is_repeated,
            "can_execute_without_approval": r.can_execute_without_approval() if r.validity_period > 0 else False,
        }
        items.append(item)
    
    return {"items": items, "total": total}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_release(
    release: ReleaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("release:create"))
):
    """创建发布单"""
    # 检查用户是否有权限操作此服务（通过角色组）
    rbac_service = RBACService(db)
    
    # 获取服务信息
    result = await db.execute(select(Service).where(Service.id == release.service_id))
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    
    # 检查角色组权限（超级管理员跳过）
    if not current_user.is_superuser:
        has_access = await rbac_service.check_user_role_group_access(
            current_user.id, 
            service_id=release.service_id,
            namespace_id=service.namespace_id
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限：您不属于该服务或命名空间的发布组"
            )
    
    release_service = ReleaseService(db)
    db_release = await release_service.create_release(
        service_id=release.service_id,
        operator_id=current_user.id,
        image_tag=release.image_tag,
        require_approval=release.require_approval,
        validity_period=release.validity_period or 0
    )
    
    # 手动构建响应数据
    return {
        "id": db_release.id,
        "service_id": db_release.service_id,
        "operator_id": db_release.operator_id,
        "image_tag": db_release.image_tag,
        "image_full_path": db_release.image_full_path,
        "previous_image": db_release.previous_image,
        "status": db_release.status,
        "strategy": db_release.strategy,
        "message": db_release.message,
        "pod_status": db_release.pod_status,
        "rollback_to": db_release.rollback_to,
        "approved_by": db_release.approved_by,
        "approved_at": db_release.approved_at,
        "started_at": db_release.started_at,
        "completed_at": db_release.completed_at,
        "created_at": db_release.created_at,
        "validity_period": db_release.validity_period,
        "validity_start_at": db_release.validity_start_at,
        "validity_end_at": db_release.validity_end_at,
        "parent_release_id": db_release.parent_release_id,
        "is_repeated": db_release.is_repeated,
        "can_execute_without_approval": False,  # 新创建的发布单默认不能免审批执行
    }


@router.get("/{release_id}")
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
    
    # 手动构建响应数据
    return {
        "id": release.id,
        "service_id": release.service_id,
        "operator_id": release.operator_id,

        "image_tag": release.image_tag,
        "image_full_path": release.image_full_path,
        "previous_image": release.previous_image,
        "status": release.status,
        "strategy": release.strategy,
        "message": release.message,
        "pod_status": release.pod_status,
        "rollback_to": release.rollback_to,
        "approved_by": release.approved_by,
        "approved_at": release.approved_at,
        "started_at": release.started_at,
        "completed_at": release.completed_at,
        "created_at": release.created_at,
        "validity_period": release.validity_period,
        "validity_start_at": release.validity_start_at,
        "validity_end_at": release.validity_end_at,
        "parent_release_id": release.parent_release_id,
        "is_repeated": release.is_repeated,
        "can_execute_without_approval": release.can_execute_without_approval() if release.validity_period > 0 else False,
    }


@router.post("/{release_id}/execute")
async def execute_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("release:execute"))
):
    """执行发布"""
    # 检查用户是否有权限操作此发布（通过角色组）
    release_service = ReleaseService(db)
    rbac_service = RBACService(db)
    
    # 获取发布记录
    result = await db.execute(select(ReleaseRecord).where(ReleaseRecord.id == release_id))
    release = result.scalar_one_or_none()
    
    if not release:
        raise HTTPException(status_code=404, detail="发布记录不存在")
    
    # 检查角色组权限（超级管理员跳过）
    if not current_user.is_superuser:
        has_access = await rbac_service.check_user_role_group_access(
            current_user.id, 
            service_id=release.service_id
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限：您不属于该服务的发布组"
            )
    
    # 检查发布单状态
    if release.status != ReleaseStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"发布单状态不正确，当前状态：{release.status.value}"
        )
    
    # 检查时效（如果设置了时效）
    if release.validity_period > 0 and release.validity_end_at:
        if datetime.now(timezone.utc) > release.validity_end_at.replace(tzinfo=timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="发布单已过期，请重新创建发布单"
            )
    
    # 将状态置为 RUNNING，让前端立即看到发布已开始
    release.status = ReleaseStatus.RUNNING
    release.started_at = datetime.utcnow()
    await db.commit()
    
    # 后台启动发布任务，立即返回
    # 必须将 task 保存到全局集合，防止被 GC 回收导致任务从未执行
    task = asyncio.create_task(_run_release_in_background(release_id, current_user.id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    
    return {
        "success": True,
        "release_id": release_id,
        "message": "发布已开始，请通过详情页查看进度",
        "status": "running"
    }


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
        
        # 如果设置了时效，计算时效开始和结束时间
        if release.validity_period and release.validity_period > 0:
            from datetime import timedelta
            release.validity_start_at = release.approved_at
            release.validity_end_at = release.approved_at + timedelta(hours=release.validity_period)
    else:
        release.status = ReleaseStatus.FAILED
        release.message = f"Rejected: {approve_data.comment or 'No comment'}"
    
    await db.commit()
    await db.refresh(release)
    
    # 手动构建响应数据
    return {
        "id": release.id,
        "service_id": release.service_id,
        "operator_id": release.operator_id,

        "image_tag": release.image_tag,
        "image_full_path": release.image_full_path,
        "previous_image": release.previous_image,
        "status": release.status,
        "strategy": release.strategy,
        "message": release.message,
        "pod_status": release.pod_status,
        "rollback_to": release.rollback_to,
        "approved_by": release.approved_by,
        "approved_at": release.approved_at,
        "started_at": release.started_at,
        "completed_at": release.completed_at,
        "created_at": release.created_at,
        "validity_period": release.validity_period,
        "validity_start_at": release.validity_start_at,
        "validity_end_at": release.validity_end_at,
        "parent_release_id": release.parent_release_id,
        "is_repeated": release.is_repeated,
        "can_execute_without_approval": release.can_execute_without_approval() if release.validity_period > 0 else False,
    }


@router.websocket("/{release_id}/progress")
async def websocket_endpoint(
    websocket: WebSocket,
    release_id: int
):
    """WebSocket 实时推送发布进度"""
    await manager.connect(websocket, release_id)
    print(f"[WebSocket] Client connected for release {release_id}")
    
    try:
        while True:
            # 每次循环创建新的数据库连接，避免长期占用
            async with AsyncSessionLocal() as db:
                try:
                    # 获取最新发布状态
                    result = await db.execute(
                        select(ReleaseRecord).where(ReleaseRecord.id == release_id)
                    )
                    release = result.scalar_one_or_none()
                    
                    if release:
                        # 初始化进度数据
                        progress = {}
                        
                        # 如果存在 pod_status，解析它
                        if release.pod_status:
                            progress = json.loads(release.pod_status)
                        
                        # 如果发布单状态已经是成功/失败，覆盖 pod_status 中的状态
                        # 避免 WebSocket 重连后发送过时的 updating 状态
                        # 注意：release.status 是 ReleaseStatus 枚举，需要用 value 比较
                        if release.status.value == 'success':
                            progress['status'] = 'completed'
                            progress['message'] = release.message or '滚动更新成功完成，所有 Pod 均已 Running'
                            print(f"[WebSocket] Release {release_id} already success, forcing status=completed")
                        elif release.status.value == 'failed':
                            progress['status'] = 'failed'
                            progress['message'] = release.message or '发布失败'
                            print(f"[WebSocket] Release {release_id} already failed, forcing status=failed")
                        
                        # 确保 pods 字段存在
                        if 'pods' not in progress:
                            progress['pods'] = []
                        
                        print(f"[WebSocket] Sending progress for release {release_id}: status={progress.get('status')}, pods_count={len(progress.get('pods', []))}")
                        await websocket.send_json(progress)
                    else:
                        print(f"[WebSocket] Release {release_id} not found")
                finally:
                    await db.close()
            
            # 每 3 秒推送一次
            await asyncio.sleep(3)
            
    except WebSocketDisconnect:
        print(f"[WebSocket] Client disconnected for release {release_id}")
        manager.disconnect(websocket, release_id)
    except Exception as e:
        print(f"[WebSocket] Error for release {release_id}: {e}")
        manager.disconnect(websocket, release_id)


from datetime import datetime


@router.post("/{release_id}/reexecute")
async def reexecute_release(
    release_id: int,
    release_data: ReleaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("release:create"))
):
    """
    在审批时效内重新执行发布（免审批）
    基于已有的父发布单创建新的发布记录，无需再次审批
    """
    release_service = ReleaseService(db)
    rbac_service = RBACService(db)
    
    # 检查父发布单是否可以在时效内免审批执行
    parent_release = await release_service.check_validity_for_reexecution(
        parent_release_id=release_id,
        operator_id=current_user.id
    )
    
    if not parent_release:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无法重新执行：发布单不存在、已过期或您没有权限"
        )
    
    # 检查用户是否有权限操作此服务
    result = await db.execute(select(Service).where(Service.id == release_data.service_id))
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在")
    
    # 检查角色组权限（超级管理员跳过）
    if not current_user.is_superuser:
        has_access = await rbac_service.check_user_role_group_access(
            current_user.id, 
            service_id=release_data.service_id,
            namespace_id=service.namespace_id
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限：您不属于该服务或命名空间的发布组"
            )
    
    # 确保是同一服务
    if release_data.service_id != parent_release.service_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重新执行发布必须使用相同的服务"
        )
    
    # 创建新的发布记录（时效内免审批，继承父发布单的时效）
    db_release = await release_service.create_release(
        service_id=release_data.service_id,
        operator_id=current_user.id,
        image_tag=release_data.image_tag,
        require_approval=False,  # 时效内免审批
        validity_period=parent_release.validity_period,  # 继承父发布单的时效
        parent_release_id=release_id
    )
    
    # 手动构建响应数据
    return {
        "id": db_release.id,
        "service_id": db_release.service_id,
        "operator_id": db_release.operator_id,
        "image_tag": db_release.image_tag,
        "image_full_path": db_release.image_full_path,
        "previous_image": db_release.previous_image,
        "status": db_release.status,
        "strategy": db_release.strategy,
        "message": db_release.message,
        "pod_status": db_release.pod_status,
        "rollback_to": db_release.rollback_to,
        "approved_by": db_release.approved_by,
        "approved_at": db_release.approved_at,
        "started_at": db_release.started_at,
        "completed_at": db_release.completed_at,
        "created_at": db_release.created_at,
        "validity_period": db_release.validity_period,
        "validity_start_at": db_release.validity_start_at,
        "validity_end_at": db_release.validity_end_at,
        "parent_release_id": db_release.parent_release_id,
        "is_repeated": db_release.is_repeated,
        "can_execute_without_approval": False,  # 新创建的子发布单默认不能免审批执行
    }


@router.get("/{release_id}/validity", response_model=dict)
async def check_release_validity(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    检查发布单的审批时效状态
    返回是否可以在时效内免审批重新执行
    """
    result = await db.execute(select(ReleaseRecord).where(ReleaseRecord.id == release_id))
    release = result.scalar_one_or_none()
    
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    
    # 检查是否是同一用户
    is_owner = release.operator_id == current_user.id
    
    # 检查时效
    can_reexecute = False
    if is_owner and release.validity_period and release.validity_period > 0:
        can_reexecute = release.can_execute_without_approval()
    
    return {
        "release_id": release_id,
        "validity_period": release.validity_period,
        "validity_start_at": release.validity_start_at,
        "validity_end_at": release.validity_end_at,
        "is_expired": release.is_validity_expired() if release.validity_period > 0 else True,
        "can_reexecute": can_reexecute,
        "is_owner": is_owner
    }
