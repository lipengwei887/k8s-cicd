from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.rbac_service import RBACService


@dataclass
class ResourceContext:
    """资源上下文，用于做 scope 判定。"""

    owner_user_id: Optional[int] = None
    org_id: Optional[int] = None
    service_id: Optional[int] = None
    namespace_id: Optional[int] = None


def _normalize_scope(scope_type: Optional[str]) -> str:
    scope = (scope_type or "all").lower()
    if scope in {"assigned", "team"}:
        return "resource_group"
    return scope


def _permission_name(permission_code: str) -> str:
    mapping = {
        "cluster:read": "查看集群",
        "cluster:create": "创建集群",
        "cluster:update": "编辑集群",
        "cluster:delete": "删除集群",
        "namespace:read": "查看命名空间",
        "namespace:create": "创建命名空间",
        "namespace:update": "编辑命名空间",
        "namespace:delete": "删除命名空间",
        "service:read": "查看服务",
        "service:create": "创建服务",
        "service:update": "编辑服务",
        "service:delete": "删除服务",
        "service:deploy": "部署服务",
        "service:config": "配置服务",
        "release:create": "创建发布",
        "release:read": "查看发布",
        "release:execute": "执行发布",
        "release:approve": "审批发布",
        "release:rollback": "回滚发布",
        "user:read": "查看用户",
        "user:manage": "管理用户",
        "role:read": "查看角色",
        "role:manage": "管理角色",
    }
    return mapping.get(permission_code, permission_code)


async def user_has_permission_code(
    db: AsyncSession,
    user: User,
    permission_code: str,
) -> bool:
    if user.is_superuser:
        return True

    rbac_service = RBACService(db)
    permissions = await rbac_service.get_user_permissions(user.id)
    return any(perm["permission_code"] == permission_code for perm in permissions)


async def authorize_permission(
    db: AsyncSession,
    user: User,
    permission_code: str,
    resource_context: Optional[ResourceContext] = None,
) -> bool:
    """
    统一权限判定：
    1. 先校验用户是否拥有权限码
    2. 如果给了资源上下文，再校验 scope
    """
    if user.is_superuser:
        return True

    rbac_service = RBACService(db)
    permissions = await rbac_service.get_user_permissions(user.id)

    for perm in permissions:
        if perm["permission_code"] != permission_code:
            continue

        scope = _normalize_scope(perm.get("scope_type"))
        if resource_context is None:
            return True

        if scope == "all":
            return True

        if scope == "self" and resource_context.owner_user_id == user.id:
            return True

        if (
            scope == "org"
            and user.org_id is not None
            and resource_context.org_id is not None
            and user.org_id == resource_context.org_id
        ):
            return True

        if scope == "resource_group":
            if await rbac_service.check_user_role_group_access(
                user.id,
                service_id=resource_context.service_id,
                namespace_id=resource_context.namespace_id,
            ):
                return True

    return False


async def ensure_permission(
    db: AsyncSession,
    user: User,
    permission_code: str,
    resource_context: Optional[ResourceContext] = None,
) -> None:
    has_permission = await authorize_permission(
        db=db,
        user=user,
        permission_code=permission_code,
        resource_context=resource_context,
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"没有权限：{_permission_name(permission_code)}",
        )


def require_permission(permission_code: str):
    from fastapi import Depends
    from app.api.v1.auth import get_current_active_user

    async def dependency(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        await ensure_permission(db, current_user, permission_code)
        return current_user

    return dependency
