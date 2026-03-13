"""
RBAC 权限管理服务
参考 JumpServer 设计
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.role import Role, RoleGroup, UserRole, RBACPermission, RolePermission, Organization, RoleType
from app.models.user import User


class RBACService:
    """RBAC 权限管理服务"""
    
    # 系统预定义角色
    SYSTEM_ROLES = {
        "super_admin": {
            "name": "超级管理员",
            "description": "拥有系统所有权限",
            "permissions": ["*:*"],
        },
        "org_admin": {
            "name": "组织管理员",
            "description": "管理本组织内所有资源",
            "permissions": [
                "cluster:read:org",
                "namespace:*:org",
                "service:*:org",
                "release:*:org",
                "user:manage:org",
                "role:read:org",
            ],
        },
        "ops_engineer": {
            "name": "运维工程师",
            "description": "负责服务部署和运维",
            "permissions": [
                "cluster:read:assigned",
                "namespace:read:assigned",
                "service:deploy:assigned",
                "service:config:assigned",
                "release:execute:assigned",
                "release:rollback:assigned",
            ],
        },
        "developer": {
            "name": "开发工程师",
            "description": "负责代码发布",
            "permissions": [
                "cluster:read:assigned",
                "namespace:read:assigned",
                "service:read:assigned",
                "release:create:assigned",
                "release:read:self",
            ],
        },
        "approver": {
            "name": "审批人",
            "description": "审批发布请求",
            "permissions": [
                "cluster:read:assigned",
                "namespace:read:assigned",
                "service:read:assigned",
                "release:approve:assigned",
                "release:read:assigned",
            ],
        },
        "viewer": {
            "name": "访客",
            "description": "只读访问权限",
            "permissions": [
                "cluster:read:assigned",
                "namespace:read:assigned",
                "service:read:assigned",
                "release:read:assigned",
            ],
        },
    }
    
    # 预定义权限列表
    SYSTEM_PERMISSIONS = [
        # 集群权限
        {"name": "查看集群", "code": "cluster:read", "resource_type": "cluster", "action": "read"},
        {"name": "创建集群", "code": "cluster:create", "resource_type": "cluster", "action": "create"},
        {"name": "编辑集群", "code": "cluster:update", "resource_type": "cluster", "action": "update"},
        {"name": "删除集群", "code": "cluster:delete", "resource_type": "cluster", "action": "delete"},
        
        # 命名空间权限
        {"name": "查看命名空间", "code": "namespace:read", "resource_type": "namespace", "action": "read"},
        {"name": "创建命名空间", "code": "namespace:create", "resource_type": "namespace", "action": "create"},
        {"name": "编辑命名空间", "code": "namespace:update", "resource_type": "namespace", "action": "update"},
        {"name": "删除命名空间", "code": "namespace:delete", "resource_type": "namespace", "action": "delete"},
        
        # 服务权限
        {"name": "查看服务", "code": "service:read", "resource_type": "service", "action": "read"},
        {"name": "创建服务", "code": "service:create", "resource_type": "service", "action": "create"},
        {"name": "编辑服务", "code": "service:update", "resource_type": "service", "action": "update"},
        {"name": "删除服务", "code": "service:delete", "resource_type": "service", "action": "delete"},
        {"name": "部署服务", "code": "service:deploy", "resource_type": "service", "action": "execute"},
        {"name": "配置服务", "code": "service:config", "resource_type": "service", "action": "update"},
        
        # 发布权限
        {"name": "查看发布", "code": "release:read", "resource_type": "release", "action": "read"},
        {"name": "创建发布", "code": "release:create", "resource_type": "release", "action": "create"},
        {"name": "执行发布", "code": "release:execute", "resource_type": "release", "action": "execute"},
        {"name": "审批发布", "code": "release:approve", "resource_type": "release", "action": "approve"},
        {"name": "回滚发布", "code": "release:rollback", "resource_type": "release", "action": "execute"},
        
        # 用户权限
        {"name": "查看用户", "code": "user:read", "resource_type": "user", "action": "read"},
        {"name": "管理用户", "code": "user:manage", "resource_type": "user", "action": "*"},
        
        # 角色权限
        {"name": "查看角色", "code": "role:read", "resource_type": "role", "action": "read"},
        {"name": "管理角色", "code": "role:manage", "resource_type": "role", "action": "*"},
    ]
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def init_system_roles(self):
        """初始化系统角色和权限"""
        # 1. 创建系统权限
        for perm_data in self.SYSTEM_PERMISSIONS:
            result = await self.db.execute(
                select(RBACPermission).where(RBACPermission.code == perm_data["code"])
            )
            if not result.scalar_one_or_none():
                permission = RBACPermission(**perm_data)
                self.db.add(permission)
        
        await self.db.commit()
        
        # 2. 创建系统角色
        for code, role_data in self.SYSTEM_ROLES.items():
            result = await self.db.execute(
                select(Role).where(Role.code == code)
            )
            if not result.scalar_one_or_none():
                role = Role(
                    name=role_data["name"],
                    code=code,
                    description=role_data["description"],
                    role_type=RoleType.SYSTEM,
                    status=1
                )
                self.db.add(role)
                await self.db.flush()
                
                # 3. 为角色分配权限
                for perm_code in role_data["permissions"]:
                    if perm_code == "*:*":
                        # 超级管理员拥有所有权限
                        all_perms = await self.db.execute(select(RBACPermission))
                        for perm in all_perms.scalars().all():
                            role_perm = RolePermission(
                                role_id=role.id,
                                permission_id=perm.id,
                                scope_type="all"
                            )
                            self.db.add(role_perm)
                    else:
                        # 解析权限编码
                        resource_action, scope = perm_code.rsplit(":", 1)
                        resource, action = resource_action.split(":")
                        
                        # 查找匹配的权限
                        perm_result = await self.db.execute(
                            select(RBACPermission).where(
                                and_(
                                    RBACPermission.resource_type == resource,
                                    RBACPermission.action == action
                                )
                            ).limit(1)
                        )
                        perm = perm_result.scalars().first()
                        if perm:
                            role_perm = RolePermission(
                                role_id=role.id,
                                permission_id=perm.id,
                                scope_type=scope
                            )
                            self.db.add(role_perm)
        
        await self.db.commit()
    
    async def get_user_permissions(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的所有权限"""
        # 获取用户的所有角色
        result = await self.db.execute(
            select(UserRole, Role).join(Role).where(
                and_(
                    UserRole.user_id == user_id,
                    Role.status == 1
                )
            )
        )
        user_roles = result.all()
        
        permissions = []
        for user_role, role in user_roles:
            # 检查角色有效期
            if user_role.valid_until and user_role.valid_until < datetime.utcnow():
                continue
            
            # 获取角色的权限
            perm_result = await self.db.execute(
                select(RolePermission, RBACPermission).join(RBACPermission).where(
                    RolePermission.role_id == role.id
                )
            )
            for role_perm, perm in perm_result.all():
                permissions.append({
                    "permission_code": perm.code,
                    "scope_type": role_perm.scope_type,
                    "resource_type": perm.resource_type,
                    "action": perm.action,
                })
        
        return permissions
    
    async def check_permission(self, user_id: int, permission_code: str, resource_id: Optional[int] = None) -> bool:
        """检查用户是否有特定权限"""
        # 获取用户信息
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return False
        
        # 超级管理员拥有所有权限
        if user.is_superuser:
            return True
        
        # 解析权限编码
        resource_type, action = permission_code.split(":")
        
        # 获取用户的权限
        permissions = await self.get_user_permissions(user_id)
        
        for perm in permissions:
            # 检查权限匹配
            if perm["resource_type"] == resource_type and perm["action"] in [action, "*"]:
                # 检查数据范围
                if perm["scope_type"] == "all":
                    return True
                elif perm["scope_type"] == "self":
                    # 只能操作自己的数据
                    return True  # 需要在外层检查资源归属
                elif perm["scope_type"] == "org":
                    # 同一组织
                    return True  # 需要在外层检查组织
                elif perm["scope_type"] == "assigned":
                    # 检查是否被分配了该资源
                    if resource_id:
                        # TODO: 检查资源分配表
                        return True
                    else:
                        # 没有指定资源ID，默认允许（后续在具体资源操作时检查）
                        return True
        
        return False
    
    async def check_user_role_group_access(self, user_id: int, service_id: Optional[int] = None, namespace_id: Optional[int] = None) -> bool:
        """检查用户是否通过角色组有权限访问指定服务或命名空间
        
        如果没有分配任何角色组，返回 False（默认无权限）
        命名空间权限包含该命名空间下的所有服务
        """
        from app.models.role import UserRoleGroup, RoleGroupService, RoleGroupNamespace
        from app.models.service import Service
        
        # 获取用户的所有角色组
        result = await self.db.execute(
            select(UserRoleGroup).where(UserRoleGroup.user_id == user_id)
        )
        user_role_groups = result.scalars().all()
        
        # 如果没有角色组，默认无权限
        if not user_role_groups:
            return False
        
        role_group_ids = [urg.role_group_id for urg in user_role_groups]
        
        # 检查服务权限（精确匹配）
        if service_id:
            result = await self.db.execute(
                select(RoleGroupService).where(
                    and_(
                        RoleGroupService.role_group_id.in_(role_group_ids),
                        RoleGroupService.service_id == service_id
                    )
                )
            )
            if result.scalar_one_or_none():
                return True
            
            # 如果服务没有直接关联，检查该服务所在命名空间是否有权限
            # 获取服务的命名空间ID
            result = await self.db.execute(
                select(Service.namespace_id).where(Service.id == service_id)
            )
            service_namespace_id = result.scalar_one_or_none()
            
            if service_namespace_id:
                result = await self.db.execute(
                    select(RoleGroupNamespace).where(
                        and_(
                            RoleGroupNamespace.role_group_id.in_(role_group_ids),
                            RoleGroupNamespace.namespace_id == service_namespace_id
                        )
                    )
                )
                if result.scalar_one_or_none():
                    return True
        
        # 检查命名空间权限
        if namespace_id:
            result = await self.db.execute(
                select(RoleGroupNamespace).where(
                    and_(
                        RoleGroupNamespace.role_group_id.in_(role_group_ids),
                        RoleGroupNamespace.namespace_id == namespace_id
                    )
                )
            )
            if result.scalar_one_or_none():
                return True
        
        return False
    
    async def get_user_role_groups(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的角色组列表"""
        from app.models.role import UserRoleGroup, RoleGroup
        
        result = await self.db.execute(
            select(RoleGroup, UserRoleGroup)
            .join(UserRoleGroup)
            .where(UserRoleGroup.user_id == user_id)
        )
        
        role_groups = []
        for rg, urg in result.all():
            role_groups.append({
                "id": rg.id,
                "name": rg.name,
                "code": rg.code,
                "description": rg.description,
            })
        
        return role_groups
    
    async def assign_role_to_user(self, user_id: int, role_id: int, valid_until: Optional[datetime] = None):
        """为用户分配角色"""
        # 检查是否已分配
        result = await self.db.execute(
            select(UserRole).where(
                and_(UserRole.user_id == user_id, UserRole.role_id == role_id)
            )
        )
        if result.scalar_one_or_none():
            raise ValueError("用户已拥有该角色")
        
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            valid_until=valid_until
        )
        self.db.add(user_role)
        await self.db.commit()
    
    async def remove_role_from_user(self, user_id: int, role_id: int):
        """移除用户的角色"""
        result = await self.db.execute(
            select(UserRole).where(
                and_(UserRole.user_id == user_id, UserRole.role_id == role_id)
            )
        )
        user_role = result.scalar_one_or_none()
        if user_role:
            await self.db.delete(user_role)
            await self.db.commit()
    
    async def create_custom_role(self, name: str, code: str, description: str, permission_ids: List[int]) -> Role:
        """创建自定义角色"""
        # 检查编码是否已存在
        result = await self.db.execute(
            select(Role).where(Role.code == code)
        )
        if result.scalar_one_or_none():
            raise ValueError(f"角色编码 {code} 已存在")
        
        role = Role(
            name=name,
            code=code,
            description=description,
            role_type=RoleType.CUSTOM,
            status=1
        )
        self.db.add(role)
        await self.db.flush()
        
        # 分配权限
        for perm_id in permission_ids:
            role_perm = RolePermission(
                role_id=role.id,
                permission_id=perm_id,
                scope_type="assigned"
            )
            self.db.add(role_perm)
        
        await self.db.commit()
        await self.db.refresh(role)
        return role
