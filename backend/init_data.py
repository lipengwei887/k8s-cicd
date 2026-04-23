"""
数据库初始化脚本
创建管理员账号和测试数据
"""
import asyncio
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User
from app.models.cluster import Cluster
from app.models.namespace import Namespace
from app.models.service import Service
from app.models.user import UserRole
from app.models.namespace import EnvType
from app.models.service import ServiceType
from app.models.role import RBACPermission
from app.services.rbac_service import RBACService
from app.core.security import get_password_hash


async def init_database():
    """初始化数据库表"""
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表创建完成")
    
    # 检查并添加缺失的列
    await add_missing_columns()


async def create_admin_user(db: AsyncSession):
    """创建管理员账号"""
    # 检查是否已存在
    result = await db.execute(select(User).where(User.username == "admin"))
    existing = result.scalar_one_or_none()
    if existing:
        print("⚠️ 管理员账号已存在")
        return
    
    admin = User(
        username="admin",
        password_hash=get_password_hash("admin123"),
        email="admin@example.com",
        real_name="管理员",
        role=UserRole.ADMIN,
        status=1
    )
    db.add(admin)
    await db.commit()
    print("✅ 管理员账号创建完成: admin / admin123")


async def init_permissions(db: AsyncSession):
    """初始化权限数据"""
    from sqlalchemy import select
    
    # 定义权限列表
    permissions = [
        # 集群管理
        {"name": "集群管理", "code": "cluster:read", "resource_type": "cluster", "action": "read"},
        {"name": "创建集群", "code": "cluster:create", "resource_type": "cluster", "action": "create"},
        {"name": "编辑集群", "code": "cluster:update", "resource_type": "cluster", "action": "update"},
        {"name": "删除集群", "code": "cluster:delete", "resource_type": "cluster", "action": "delete"},
        # 命名空间管理
        {"name": "命名空间管理", "code": "namespace:read", "resource_type": "namespace", "action": "read"},
        {"name": "创建命名空间", "code": "namespace:create", "resource_type": "namespace", "action": "create"},
        {"name": "编辑命名空间", "code": "namespace:update", "resource_type": "namespace", "action": "update"},
        {"name": "删除命名空间", "code": "namespace:delete", "resource_type": "namespace", "action": "delete"},
        {"name": "命名空间全部操作", "code": "namespace:*", "resource_type": "namespace", "action": "*"},
        # 服务管理
        {"name": "服务管理", "code": "service:read", "resource_type": "service", "action": "read"},
        {"name": "创建服务", "code": "service:create", "resource_type": "service", "action": "create"},
        {"name": "编辑服务", "code": "service:update", "resource_type": "service", "action": "update"},
        {"name": "删除服务", "code": "service:delete", "resource_type": "service", "action": "delete"},
        {"name": "部署服务", "code": "service:deploy", "resource_type": "service", "action": "deploy"},
        {"name": "服务配置", "code": "service:config", "resource_type": "service", "action": "config"},
        {"name": "服务全部操作", "code": "service:*", "resource_type": "service", "action": "*"},
        # 发布管理
        {"name": "发布管理", "code": "release:read", "resource_type": "release", "action": "read"},
        {"name": "创建发布", "code": "release:create", "resource_type": "release", "action": "create"},
        {"name": "执行发布", "code": "release:execute", "resource_type": "release", "action": "execute"},
        {"name": "审批发布", "code": "release:approve", "resource_type": "release", "action": "approve"},
        {"name": "回滚发布", "code": "release:rollback", "resource_type": "release", "action": "rollback"},
        {"name": "发布全部操作", "code": "release:*", "resource_type": "release", "action": "*"},
        # 用户管理
        {"name": "用户管理", "code": "user:read", "resource_type": "user", "action": "read"},
        {"name": "用户管理", "code": "user:manage", "resource_type": "user", "action": "manage"},
        {"name": "用户全部操作", "code": "user:*", "resource_type": "user", "action": "*"},
        # 角色管理
        {"name": "角色管理", "code": "role:read", "resource_type": "role", "action": "read"},
        {"name": "角色管理", "code": "role:manage", "resource_type": "role", "action": "manage"},
        {"name": "角色全部操作", "code": "role:*", "resource_type": "role", "action": "*"},
    ]
    
    added_count = 0
    for perm_data in permissions:
        result = await db.execute(
            select(RBACPermission).where(RBACPermission.code == perm_data["code"])
        )
        existing = result.scalar_one_or_none()
        if not existing:
            perm = RBACPermission(
                name=perm_data["name"],
                code=perm_data["code"],
                permission_type="api",
                resource_type=perm_data["resource_type"],
                action=perm_data["action"],
                status=1
            )
            db.add(perm)
            added_count += 1
    
    if added_count > 0:
        await db.commit()
        print(f"✅ 新增权限数据: {added_count} 个")
    else:
        print("⚠️ 权限数据已存在")


async def create_test_data(db: AsyncSession):
    """创建测试数据"""
    from sqlalchemy import select
    
    # 检查集群是否已存在
    result = await db.execute(select(Cluster).where(Cluster.name == "test"))
    cluster = result.scalar_one_or_none()
    if not cluster:
        cluster = Cluster(
            name="test",
            display_name="临时测试集群",
            api_server="https://kubernetes.default.svc",
            status=1,
            description="测试环境集群"
        )
        db.add(cluster)
        await db.commit()
        await db.refresh(cluster)
    print(f"✅ 集群创建完成: {cluster.name}")
    
    # 检查命名空间是否已存在
    result = await db.execute(select(Namespace).where(Namespace.cluster_id == cluster.id))
    namespaces = list(result.scalars().all())
    
    if len(namespaces) < 4:
        ns_names = ["tczxc-prod-a", "tczxc-prod-b", "tczxc-test", "tczxc-dev"]
        ns_display = ["生产环境A", "生产环境B", "测试环境", "开发环境"]
        env_types = [EnvType.PROD, EnvType.PROD, EnvType.TEST, EnvType.DEV]
        
        for i, name in enumerate(ns_names):
            result = await db.execute(select(Namespace).where(
                and_(Namespace.cluster_id == cluster.id, Namespace.name == name)
            ))
            ns = result.scalar_one_or_none()
            if not ns:
                ns = Namespace(
                    cluster_id=cluster.id, name=name, 
                    display_name=ns_display[i], 
                    env_type=env_types[i], status=1
                )
                db.add(ns)
                await db.flush()
                namespaces.append(ns)
        
        await db.commit()
    
    # 刷新获取命名空间 ID
    for ns in namespaces:
        await db.refresh(ns)
    print(f"✅ 命名空间创建完成: {len(namespaces)} 个")
    
    # 创建服务
    services = [
        Service(
            namespace_id=namespaces[0].id, name="user-service", display_name="用户服务",
            type=ServiceType.DEPLOYMENT, deploy_name="user-service",
            container_name="user-service", harbor_project="tczxc", harbor_repo="user-service",
            port=8080, replicas=3, status=1
        ),
        Service(
            namespace_id=namespaces[0].id, name="order-service", display_name="订单服务",
            type=ServiceType.DEPLOYMENT, deploy_name="order-service",
            container_name="order-service", harbor_project="tczxc", harbor_repo="order-service",
            port=8080, replicas=3, status=1
        ),
        Service(
            namespace_id=namespaces[0].id, name="payment-service", display_name="支付服务",
            type=ServiceType.DEPLOYMENT, deploy_name="payment-service",
            container_name="payment-service", harbor_project="tczxc", harbor_repo="payment-service",
            port=8080, replicas=2, status=1
        ),
        Service(
            namespace_id=namespaces[2].id, name="test-app", display_name="测试应用",
            type=ServiceType.DEPLOYMENT, deploy_name="test-app",
            container_name="test-app", harbor_project="tczxc", harbor_repo="test-app",
            port=8080, replicas=1, status=1
        ),
    ]
    for svc in services:
        db.add(svc)
    await db.commit()
    print(f"✅ 服务创建完成: {len(services)} 个")


async def add_missing_columns():
    """添加可能缺失的列"""
    from sqlalchemy import text
    async with engine.begin() as conn:
        # 检查 users 表的列 - MySQL 8.0 语法
        try:
            # 先检查列是否存在
            result = await conn.execute(text("SHOW COLUMNS FROM users LIKE 'org_id'"))
            if result.fetchone() is None:
                await conn.execute(text("ALTER TABLE users ADD COLUMN org_id INT NULL"))
                print("✅ 添加 org_id 列")
            else:
                print("⚠️ org_id 列已存在")
        except Exception as e:
            print(f"⚠️ org_id 列处理失败: {e}")
        
        try:
            result = await conn.execute(text("SHOW COLUMNS FROM users LIKE 'is_superuser'"))
            if result.fetchone() is None:
                await conn.execute(text("ALTER TABLE users ADD COLUMN is_superuser BOOLEAN DEFAULT FALSE"))
                print("✅ 添加 is_superuser 列")
            else:
                print("⚠️ is_superuser 列已存在")
        except Exception as e:
            print(f"⚠️ is_superuser 列处理失败: {e}")
        
        try:
            result = await conn.execute(text("SHOW COLUMNS FROM users LIKE 'mfa_enabled'"))
            if result.fetchone() is None:
                await conn.execute(text("ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT FALSE"))
                print("✅ 添加 mfa_enabled 列")
            else:
                print("⚠️ mfa_enabled 列已存在")
        except Exception as e:
            print(f"⚠️ mfa_enabled 列处理失败: {e}")


async def main():
    """主函数"""
    print("🚀 开始初始化数据库...")
    
    # 创建表
    await init_database()
    
    # 创建数据
    async with AsyncSessionLocal() as db:
        try:
            await create_admin_user(db)
            await init_permissions(db)
            
            # 初始化系统角色和权限关联
            rbac_service = RBACService(db)
            
            # 检查角色是否已存在
            from sqlalchemy import select
            from app.models.role import Role, RoleType
            result = await db.execute(select(Role).where(Role.role_type == RoleType.SYSTEM))
            existing_roles = result.scalars().all()
            
            if not existing_roles:
                await rbac_service.init_system_roles()
            else:
                print("⚠️ 系统角色已存在")
            
            await create_test_data(db)
            print("\n✨ 数据库初始化完成!")
            print("\n登录信息:")
            print("  用户名: admin")
            print("  密码: admin123")
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            await db.rollback()


if __name__ == "__main__":
    asyncio.run(main())
