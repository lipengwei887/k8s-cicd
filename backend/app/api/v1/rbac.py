"""
RBAC 权限管理 API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from app.database import get_db
from app.core.authorization import require_permission
from app.models.role import Role, RoleGroup, UserRole, RBACPermission, RolePermission, Organization, RoleType
from app.models.user import User
from app.services.rbac_service import RBACService
from app.api.v1.auth import get_current_user

router = APIRouter(tags=["RBAC权限管理"])


# ============ 请求/响应模型 ============

class RoleCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    permission_ids: List[int]


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None
    permission_ids: Optional[List[int]] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str]
    role_type: str
    status: int
    created_at: str
    
    class Config:
        from_attributes = True


class RBACPermissionResponse(BaseModel):
    id: int
    name: str
    code: str
    resource_type: str
    action: str
    
    class Config:
        from_attributes = True


class UserRoleAssign(BaseModel):
    user_id: int
    role_id: int


class OrganizationCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    parent_id: Optional[int] = None


# ============ 角色管理 API ============

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    role_type: Optional[str] = None,
    status: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取角色列表"""
    query = select(Role)
    
    if role_type:
        query = query.where(Role.role_type == role_type)
    if status is not None:
        query = query.where(Role.status == status)
    
    result = await db.execute(query.order_by(Role.created_at.desc()))
    roles = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "name": r.name,
            "code": r.code,
            "description": r.description,
            "role_type": r.role_type.value,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in roles
    ]


@router.get("/roles/{role_id}")
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取角色详情"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 获取角色权限
    perm_result = await db.execute(
        select(RBACPermission).join(RolePermission).where(RolePermission.role_id == role_id)
    )
    permissions = perm_result.scalars().all()
    
    return {
        "id": role.id,
        "name": role.name,
        "code": role.code,
        "description": role.description,
        "role_type": role.role_type.value,
        "status": role.status,
        "permissions": [
            {"id": p.id, "name": p.name, "code": p.code, "resource_type": p.resource_type}
            for p in permissions
        ],
        "created_at": role.created_at.isoformat() if role.created_at else None
    }


@router.post("/roles", response_model=RoleResponse)
async def create_role(
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:manage"))
):
    """创建自定义角色"""
    rbac_service = RBACService(db)
    
    try:
        role = await rbac_service.create_custom_role(
            name=data.name,
            code=data.code,
            description=data.description,
            permission_ids=data.permission_ids
        )
        return {
            "id": role.id,
            "name": role.name,
            "code": role.code,
            "description": role.description,
            "role_type": role.role_type.value,
            "status": role.status,
            "created_at": role.created_at.isoformat() if role.created_at else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error creating role: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/roles/{role_id}")
async def update_role(
    role_id: int,
    data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:manage"))
):
    """更新角色"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 系统角色不允许修改
    if role.role_type == RoleType.SYSTEM:
        raise HTTPException(status_code=403, detail="系统角色不允许修改")
    
    if data.name:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.status is not None:
        role.status = data.status
    
    # 更新权限
    if data.permission_ids is not None:
        # 删除旧权限
        await db.execute(
            RolePermission.__table__.delete().where(RolePermission.role_id == role_id)
        )
        
        # 添加新权限
        for perm_id in data.permission_ids:
            role_perm = RolePermission(
                role_id=role_id,
                permission_id=perm_id,
                scope_type="assigned"
            )
            db.add(role_perm)
    
    await db.commit()
    await db.refresh(role)
    
    return {
        "id": role.id,
        "name": role.name,
        "code": role.code,
        "description": role.description,
        "role_type": role.role_type.value,
        "status": role.status,
        "created_at": role.created_at.isoformat() if role.created_at else None
    }


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:manage"))
):
    """删除角色"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 系统角色不允许删除
    if role.role_type == RoleType.SYSTEM:
        raise HTTPException(status_code=403, detail="系统角色不允许删除")
    
    await db.delete(role)
    await db.commit()
    
    return {"message": "角色已删除"}


# ============ 权限管理 API ============

@router.get("/permissions", response_model=List[RBACPermissionResponse])
async def list_permissions(
    resource_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取权限列表"""
    query = select(RBACPermission).where(RBACPermission.status == 1)
    
    if resource_type:
        query = query.where(RBACPermission.resource_type == resource_type)
    
    result = await db.execute(query.order_by(RBACPermission.code))
    permissions = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "code": p.code,
            "resource_type": p.resource_type,
            "action": p.action
        }
        for p in permissions
    ]


# ============ 用户角色管理 API ============

@router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:read"))
):
    """获取用户的角色"""
    result = await db.execute(
        select(UserRole, Role).join(Role).where(UserRole.user_id == user_id)
    )
    user_roles = result.all()
    
    return [
        {
            "id": ur.id,
            "role_id": role.id,
            "role_name": role.name,
            "role_code": role.code,
            "valid_until": ur.valid_until.isoformat() if ur.valid_until else None,
            "created_at": ur.created_at.isoformat() if ur.created_at else None
        }
        for ur, role in user_roles
    ]


@router.post("/users/assign-role")
async def assign_role_to_user(
    data: UserRoleAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage"))
):
    """为用户分配角色"""
    rbac_service = RBACService(db)
    
    try:
        await rbac_service.assign_role_to_user(data.user_id, data.role_id)
        return {"message": "角色分配成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error assigning role: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage"))
):
    """移除用户的角色"""
    rbac_service = RBACService(db)
    await rbac_service.remove_role_from_user(user_id, role_id)
    return {"message": "角色已移除"}


# ============ 组织管理 API ============

@router.get("/organizations")
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取组织列表"""
    result = await db.execute(
        select(Organization).where(Organization.status == 1).order_by(Organization.created_at)
    )
    orgs = result.scalars().all()
    
    return [
        {
            "id": o.id,
            "name": o.name,
            "code": o.code,
            "description": o.description,
            "parent_id": o.parent_id
        }
        for o in orgs
    ]


@router.post("/organizations")
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:manage"))
):
    """创建组织"""
    # 检查编码是否已存在
    result = await db.execute(select(Organization).where(Organization.code == data.code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="组织编码已存在")
    
    org = Organization(
        name=data.name,
        code=data.code,
        description=data.description,
        parent_id=data.parent_id
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    
    return {
        "id": org.id,
        "name": org.name,
        "code": org.code,
        "description": org.description,
        "parent_id": org.parent_id
    }


# ============ 初始化 API ============

@router.post("/init")
async def init_rbac(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """初始化 RBAC 系统（仅超级管理员）"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="只有超级管理员可以初始化")
    
    rbac_service = RBACService(db)
    await rbac_service.init_system_roles()
    
    return {"message": "RBAC 系统初始化成功"}


# ============ 权限检查 API ============

@router.get("/check")
async def check_permission(
    permission: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查当前用户是否有特定权限"""
    rbac_service = RBACService(db)
    has_perm = await rbac_service.check_permission(current_user.id, permission)
    
    return {
        "permission": permission,
        "has_permission": has_perm
    }


@router.get("/my-permissions")
async def get_my_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """获取当前用户的所有权限"""
    rbac_service = RBACService(db)
    permissions = await rbac_service.get_user_permissions(current_user.id)
    role_groups = await rbac_service.get_user_role_groups(current_user.id)
    
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "is_superuser": current_user.is_superuser,
        "permissions": permissions,
        "role_groups": role_groups
    }


# ============ 角色组管理 API ============

@router.get("/role-groups")
async def list_role_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:manage"))
):
    """获取角色组列表"""
    from app.models.role import RoleGroup
    
    result = await db.execute(
        select(RoleGroup).where(RoleGroup.status == 1).order_by(RoleGroup.created_at)
    )
    groups = result.scalars().all()
    
    return [
        {
            "id": g.id,
            "name": g.name,
            "code": g.code,
            "description": g.description,
            "created_at": g.created_at.isoformat() if g.created_at else None
        }
        for g in groups
    ]


@router.post("/role-groups")
async def create_role_group(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:read"))
):
    """创建角色组"""
    from app.models.role import RoleGroup
    
    # 检查编码是否已存在
    result = await db.execute(
        select(RoleGroup).where(RoleGroup.code == data.get("code"))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="角色组编码已存在")
    
    group = RoleGroup(
        name=data.get("name"),
        code=data.get("code"),
        description=data.get("description"),
        status=1
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    
    return {
        "id": group.id,
        "name": group.name,
        "code": group.code,
        "description": group.description,
        "created_at": group.created_at.isoformat() if group.created_at else None
    }


@router.get("/role-groups/{group_id}")
async def get_role_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:manage"))
):
    """获取角色组详情"""
    from app.models.role import RoleGroup, RoleGroupService, RoleGroupNamespace
    from app.models.service import Service
    from app.models.namespace import Namespace
    
    result = await db.execute(select(RoleGroup).where(RoleGroup.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="角色组不存在")
    
    # 获取关联的服务
    services_result = await db.execute(
        select(Service)
        .join(RoleGroupService)
        .where(RoleGroupService.role_group_id == group_id)
    )
    services = services_result.scalars().all()
    
    # 获取关联的命名空间
    namespaces_result = await db.execute(
        select(Namespace)
        .join(RoleGroupNamespace)
        .where(RoleGroupNamespace.role_group_id == group_id)
    )
    namespaces = namespaces_result.scalars().all()
    
    return {
        "id": group.id,
        "name": group.name,
        "code": group.code,
        "description": group.description,
        "services": [{"id": s.id, "name": s.name, "display_name": s.display_name} for s in services],
        "namespaces": [{"id": n.id, "name": n.name} for n in namespaces],
        "created_at": group.created_at.isoformat() if group.created_at else None
    }


@router.put("/role-groups/{group_id}")
async def update_role_group(
    group_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:manage"))
):
    """更新角色组"""
    from app.models.role import RoleGroup
    
    result = await db.execute(select(RoleGroup).where(RoleGroup.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="角色组不存在")
    
    if "name" in data:
        group.name = data["name"]
    if "description" in data:
        group.description = data["description"]
    
    await db.commit()
    await db.refresh(group)
    
    return {
        "id": group.id,
        "name": group.name,
        "code": group.code,
        "description": group.description
    }


@router.delete("/role-groups/{group_id}")
async def delete_role_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:manage"))
):
    """删除角色组"""
    from app.models.role import RoleGroup
    
    result = await db.execute(select(RoleGroup).where(RoleGroup.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="角色组不存在")
    
    await db.delete(group)
    await db.commit()
    
    return {"message": "角色组已删除"}


@router.post("/role-groups/{group_id}/services")
async def add_service_to_role_group(
    group_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:manage"))
):
    """添加服务到角色组"""
    from app.models.role import RoleGroup, RoleGroupService
    
    result = await db.execute(select(RoleGroup).where(RoleGroup.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="角色组不存在")
    
    service_id = data.get("service_id")
    
    # 检查是否已存在
    result = await db.execute(
        select(RoleGroupService).where(
            and_(RoleGroupService.role_group_id == group_id, RoleGroupService.service_id == service_id)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="服务已在此角色组中")
    
    rgs = RoleGroupService(role_group_id=group_id, service_id=service_id)
    db.add(rgs)
    await db.commit()
    
    return {"message": "服务已添加"}


@router.delete("/role-groups/{group_id}/services/{service_id}")
async def remove_service_from_role_group(
    group_id: int,
    service_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:manage"))
):
    """从角色组移除服务"""
    from app.models.role import RoleGroupService
    
    result = await db.execute(
        select(RoleGroupService).where(
            and_(RoleGroupService.role_group_id == group_id, RoleGroupService.service_id == service_id)
        )
    )
    rgs = result.scalar_one_or_none()
    
    if not rgs:
        raise HTTPException(status_code=404, detail="服务不在此角色组中")
    
    await db.delete(rgs)
    await db.commit()
    
    return {"message": "服务已移除"}


@router.post("/role-groups/{group_id}/namespaces")
async def add_namespace_to_role_group(
    group_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage"))
):
    """添加命名空间到角色组"""
    from app.models.role import RoleGroup, RoleGroupNamespace
    
    result = await db.execute(select(RoleGroup).where(RoleGroup.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="角色组不存在")
    
    namespace_id = data.get("namespace_id")
    
    # 检查是否已存在
    result = await db.execute(
        select(RoleGroupNamespace).where(
            and_(RoleGroupNamespace.role_group_id == group_id, RoleGroupNamespace.namespace_id == namespace_id)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="命名空间已在此角色组中")
    
    rgn = RoleGroupNamespace(role_group_id=group_id, namespace_id=namespace_id)
    db.add(rgn)
    await db.commit()
    
    return {"message": "命名空间已添加"}


@router.delete("/role-groups/{group_id}/namespaces/{namespace_id}")
async def remove_namespace_from_role_group(
    group_id: int,
    namespace_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage"))
):
    """从角色组移除命名空间"""
    from app.models.role import RoleGroupNamespace
    
    result = await db.execute(
        select(RoleGroupNamespace).where(
            and_(RoleGroupNamespace.role_group_id == group_id, RoleGroupNamespace.namespace_id == namespace_id)
        )
    )
    rgn = result.scalar_one_or_none()
    
    if not rgn:
        raise HTTPException(status_code=404, detail="命名空间不在此角色组中")
    
    await db.delete(rgn)
    await db.commit()
    
    return {"message": "命名空间已移除"}


@router.post("/users/{user_id}/role-groups")
async def assign_role_group_to_user(
    user_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user:read"))
):
    """为用户分配角色组"""
    from app.models.role import RoleGroup, UserRoleGroup
    from app.models.user import User
    
    # 检查用户是否存在
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    group_id = data.get("role_group_id")
    
    # 检查角色组是否存在
    result = await db.execute(select(RoleGroup).where(RoleGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="角色组不存在")
    
    # 检查是否已分配
    result = await db.execute(
        select(UserRoleGroup).where(
            and_(UserRoleGroup.user_id == user_id, UserRoleGroup.role_group_id == group_id)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户已在此角色组中")
    
    urg = UserRoleGroup(user_id=user_id, role_group_id=group_id)
    db.add(urg)
    await db.commit()
    
    return {"message": "角色组已分配"}


@router.delete("/users/{user_id}/role-groups/{group_id}")
async def remove_role_group_from_user(
    user_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从用户移除角色组"""
    from app.models.role import UserRoleGroup
    
    result = await db.execute(
        select(UserRoleGroup).where(
            and_(UserRoleGroup.user_id == user_id, UserRoleGroup.role_group_id == group_id)
        )
    )
    urg = result.scalar_one_or_none()
    
    if not urg:
        raise HTTPException(status_code=404, detail="用户不在此角色组中")
    
    await db.delete(urg)
    await db.commit()
    
    return {"message": "角色组已移除"}


@router.get("/users/{user_id}/role-groups")
async def get_user_role_groups_api(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户的角色组列表"""
    from app.models.role import RoleGroup, UserRoleGroup
    
    result = await db.execute(
        select(RoleGroup)
        .join(UserRoleGroup)
        .where(UserRoleGroup.user_id == user_id)
    )
    groups = result.scalars().all()
    
    return [
        {
            "id": g.id,
            "name": g.name,
            "code": g.code,
            "description": g.description
        }
        for g in groups
    ]
