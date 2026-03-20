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
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.api.v1.auth import get_current_active_user, require_admin
from app.core.security import get_password_hash
from app.services.rbac_service import RBACService

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


# 用户角色管理 API (使用RBAC)
@router.get("/{user_id}/roles", dependencies=[Depends(require_admin)])
async def get_user_roles(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户的RBAC角色列表"""
    from app.models.role import UserRole, Role
    
    result = await db.execute(
        select(Role, UserRole)
        .join(UserRole, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user_id, Role.status == 1)
    )
    
    roles = []
    for role, user_role in result.all():
        roles.append({
            "id": role.id,
            "name": role.name,
            "code": role.code,
            "role_type": role.role_type.value if role.role_type else None,
            "valid_from": user_role.valid_from,
            "valid_until": user_role.valid_until
        })
    
    return {"items": roles}


@router.get("/{user_id}/permissions", dependencies=[Depends(require_admin)])
async def get_user_permissions(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户的RBAC权限列表"""
    rbac_service = RBACService(db)
    permissions = await rbac_service.get_user_permissions(user_id)
    return {"items": permissions}


@router.post("/{user_id}/roles/{role_id}", dependencies=[Depends(require_admin)])
async def assign_role_to_user(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """为用户分配角色"""
    rbac_service = RBACService(db)
    
    try:
        await rbac_service.assign_role_to_user(user_id, role_id)
        return {"message": "角色分配成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}/roles/{role_id}", dependencies=[Depends(require_admin)])
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """移除用户的角色"""
    from app.models.role import UserRole
    
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id
        )
    )
    user_role = result.scalar_one_or_none()
    
    if not user_role:
        raise HTTPException(status_code=404, detail="用户未拥有该角色")
    
    await db.delete(user_role)
    await db.commit()
    
    return {"message": "角色移除成功"}
