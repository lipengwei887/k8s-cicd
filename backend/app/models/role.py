from sqlalchemy import Column, Integer, String, Enum, ForeignKey, TIMESTAMP, Boolean, Text, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class RoleType(str, enum.Enum):
    SYSTEM = "system"    # 系统内置角色，不可删除
    CUSTOM = "custom"    # 自定义角色


class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(64), nullable=False)           # 角色名称，如"运维工程师"
    code = Column(String(64), unique=True, nullable=False)  # 角色编码，如"ops_engineer"
    description = Column(Text)                          # 角色描述
    
    role_type = Column(Enum(RoleType), default=RoleType.CUSTOM)  # 角色类型
    status = Column(Integer, default=1)                 # 0-禁用, 1-启用
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # 关系
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    users = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")


class RoleGroup(Base):
    __tablename__ = "role_groups"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(64), nullable=False)           # 组名称，如"支付组"
    code = Column(String(64), unique=True, nullable=False)  # 组编码
    description = Column(Text)
    
    parent_id = Column(Integer, ForeignKey("role_groups.id", ondelete="SET NULL"), nullable=True)
    status = Column(Integer, default=1)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # 关系
    parent = relationship("RoleGroup", remote_side=[id], backref="children")
    services = relationship("RoleGroupService", back_populates="role_group", cascade="all, delete-orphan")
    namespaces = relationship("RoleGroupNamespace", back_populates="role_group", cascade="all, delete-orphan")
    users = relationship("UserRoleGroup", back_populates="role_group", cascade="all, delete-orphan")


class UserRole(Base):
    __tablename__ = "user_roles"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    
    # 有效期控制
    valid_from = Column(TIMESTAMP, nullable=True)       # 生效时间
    valid_until = Column(TIMESTAMP, nullable=True)      # 过期时间
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="users")


class RBACPermission(Base):
    __tablename__ = "rbac_permissions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(64), nullable=False)           # 权限名称，如"发布服务"
    code = Column(String(128), unique=True, nullable=False)  # 权限编码，如"service:deploy"
    
    permission_type = Column(String(32), default="api")  # menu-菜单, button-按钮, api-接口, data-数据
    resource_type = Column(String(32))                   # cluster, namespace, service, release, user, role
    action = Column(String(32))                          # create, read, update, delete, execute, approve
    
    parent_id = Column(Integer, ForeignKey("rbac_permissions.id", ondelete="SET NULL"), nullable=True)
    status = Column(Integer, default=1)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 关系
    parent = relationship("RBACPermission", remote_side=[id], backref="children")
    roles = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(Integer, ForeignKey("rbac_permissions.id", ondelete="CASCADE"), nullable=False)
    
    scope_type = Column(String(32), default="all")      # all-全部, org-本组织, team-本团队, self-仅自己, assigned-分配的
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 关系
    role = relationship("Role", back_populates="permissions")
    permission = relationship("RBACPermission", back_populates="roles")


# 角色组与服务关联表（数据权限）
class RoleGroupService(Base):
    __tablename__ = "role_group_services"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_group_id = Column(Integer, ForeignKey("role_groups.id", ondelete="CASCADE"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 关系
    role_group = relationship("RoleGroup", back_populates="services")
    service = relationship("Service", back_populates="role_groups")


# 角色组与命名空间关联表（数据权限）
class RoleGroupNamespace(Base):
    __tablename__ = "role_group_namespaces"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_group_id = Column(Integer, ForeignKey("role_groups.id", ondelete="CASCADE"), nullable=False)
    namespace_id = Column(Integer, ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=False)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 关系
    role_group = relationship("RoleGroup", back_populates="namespaces")
    namespace = relationship("Namespace", back_populates="role_groups")


# 用户与角色组关联表
class UserRoleGroup(Base):
    __tablename__ = "user_role_groups"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_group_id = Column(Integer, ForeignKey("role_groups.id", ondelete="CASCADE"), nullable=False)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    # 联合唯一索引
    __table_args__ = (
        UniqueConstraint('user_id', 'role_group_id', name='uix_user_role_group'),
    )
    
    # 关系
    user = relationship("User", back_populates="role_groups")
    role_group = relationship("RoleGroup", back_populates="users")


class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    code = Column(String(64), unique=True, nullable=False)
    description = Column(Text)
    
    parent_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    status = Column(Integer, default=1)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    # 关系
    parent = relationship("Organization", remote_side=[id], backref="children")
