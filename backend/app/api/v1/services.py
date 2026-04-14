from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional

from app.database import get_db
from app.models.service import Service
from app.models.namespace import Namespace
from app.api.v1.auth import get_current_active_user
from app.models.user import User

router = APIRouter()


@router.get("")
async def list_services(
    skip: int = 0,
    limit: int = 100,
    namespace_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取服务列表"""
    query = select(Service).where(Service.status == 1)
    
    if namespace_id:
        query = query.where(Service.namespace_id == namespace_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    services = result.scalars().all()
    
    # 获取总数
    count_query = select(func.count(Service.id)).where(Service.status == 1)
    if namespace_id:
        count_query = count_query.where(Service.namespace_id == namespace_id)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    return {"items": services, "total": total}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_service(
    service_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建服务"""
    db_service = Service(**service_data)
    db.add(db_service)
    await db.commit()
    await db.refresh(db_service)
    
    return db_service


@router.get("/{service_id}")
async def get_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取服务详情"""
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return service


@router.get("/{service_id}/images")
async def get_service_images(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取服务的可用镜像版本 (从 Harbor)"""
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # TODO: 从 Harbor API 获取镜像标签列表
    # 这里返回模拟数据
    return {
        "items": [
            "v1.0.0",
            "v1.0.1",
            "v1.1.0",
            "latest"
        ]
    }


@router.post("/batch-names")
async def get_service_names_batch(
    service_ids: List[int],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    批量获取服务名称（用于发布记录展示优化）
    只返回 id、name、display_name、namespace_id、namespace_name 字段，避免加载大量数据
    """
    if not service_ids:
        return {}
    
    # 去重
    unique_ids = list(set(service_ids))
    
    # 批量查询，JOIN namespace 获取命名空间信息
    result = await db.execute(
        select(Service.id, Service.name, Service.display_name, Service.namespace_id, Namespace.name, Namespace.display_name)
        .join(Namespace, Service.namespace_id == Namespace.id)
        .where(Service.id.in_(unique_ids))
        .where(Service.status == 1)
    )
    
    # 转换为字典 {id: {name, display_name, namespace_id, namespace_name}}
    services_map = {}
    for row in result.fetchall():
        services_map[row[0]] = {
            "name": row[1],
            "display_name": row[2],
            "namespace_id": row[3],
            "namespace_name": row[4] or row[2]  # display_name 优先，否则用 name
        }
    
    return services_map
