"""
人员管理 API
管理员功能：新增、删除、修改用户
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.models.permission import Permission, PermissionRole
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.api.v1.auth import get_current_active_user, require_admin
from app.core.security import get_password_hash

router = APIRouter()


@router.get("")
async def list_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户列表"""
    query = select(User)
    
    if role:
        query = query.where(User.role == role)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    # 获取总数
    count_result = await db.execute(select(func.count(User.id)))
    total = count_result.scalar()
    
    # 返回基本信息（不包含敏感字段）
    user_list = []
    for user in users:
        user_list.append({
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "role": user.role.value if user.role else None,
            "email": user.email,
            "status": user.status
        })
    
    return {"items": user_list, "total": total}


@router.post("", dependencies=[Depends(require_admin)], status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建用户 (管理员)"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_data['username']))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == user_data['email']))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # 创建用户
    new_user = User(
        username=user_data['username'],
        password_hash=get_password_hash(user_data['password']),
        email=user_data['email'],
        real_name=user_data.get('real_name'),
        role=UserRole(user_data.get('role', 'developer')),
        status=1
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.get("/{user_id}", dependencies=[Depends(require_admin)])
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户详情 (管理员)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.put("/{user_id}", dependencies=[Depends(require_admin)])
async def update_user(
    user_id: int,
    user_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新用户信息 (管理员)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 更新字段
    if 'email' in user_data:
        user.email = user_data['email']
    if 'real_name' in user_data:
        user.real_name = user_data['real_name']
    if 'role' in user_data:
        user.role = UserRole(user_data['role'])
    if 'status' in user_data:
        user.status = user_data['status']
    if 'password' in user_data:
        user.password_hash = get_password_hash(user_data['password'])
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除用户 (软删除) (管理员)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 不能删除自己
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    user.status = 0  # 软删除
    await db.commit()
    
    return {"message": "User deleted successfully"}


# 权限管理 API
@router.get("/{user_id}/permissions", dependencies=[Depends(require_admin)])
async def get_user_permissions(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户权限列表"""
    result = await db.execute(
        select(Permission).where(Permission.user_id == user_id)
    )
    permissions = result.scalars().all()
    
    return {"items": permissions}


@router.post("/{user_id}/permissions", dependencies=[Depends(require_admin)])
async def add_user_permission(
    user_id: int,
    permission_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """添加用户权限"""
    # 检查用户是否存在
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")
    
    # 创建权限
    new_permission = Permission(
        user_id=user_id,
        cluster_id=permission_data.get('cluster_id'),
        namespace_id=permission_data.get('namespace_id'),
        role=PermissionRole(permission_data['role'])
    )
    
    db.add(new_permission)
    await db.commit()
    await db.refresh(new_permission)
    
    return new_permission


@router.delete("/{user_id}/permissions/{permission_id}", dependencies=[Depends(require_admin)])
async def remove_user_permission(
    user_id: int,
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除用户权限"""
    result = await db.execute(
        select(Permission).where(Permission.id == permission_id, Permission.user_id == user_id)
    )
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    await db.delete(permission)
    await db.commit()
    
    return {"message": "Permission removed successfully"}
