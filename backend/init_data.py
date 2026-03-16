"""
数据库初始化脚本
创建管理员账号和测试数据
"""
import asyncio
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
    from sqlalchemy import select
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
    
    # 检查是否已有权限数据
    result = await db.execute(select(RBACPermission))
    existing = result.scalars().all()
    if existing:
        print("⚠️ 权限数据已存在")
        return
    
    # 定义权限列表
    permissions = [
        # 集群管理
        RBACPermission(name="集群管理", code="cluster:read", permission_type="api", resource_type="cluster", action="read", status=1),
        RBACPermission(name="创建集群", code="cluster:create", permission_type="api", resource_type="cluster", action="create", status=1),
        RBACPermission(name="编辑集群", code="cluster:update", permission_type="api", resource_type="cluster", action="update", status=1),
        RBACPermission(name="删除集群", code="cluster:delete", permission_type="api", resource_type="cluster", action="delete", status=1),
        # 命名空间管理
        RBACPermission(name="命名空间管理", code="namespace:read", permission_type="api", resource_type="namespace", action="read", status=1),
        RBACPermission(name="创建命名空间", code="namespace:create", permission_type="api", resource_type="namespace", action="create", status=1),
        RBACPermission(name="编辑命名空间", code="namespace:update", permission_type="api", resource_type="namespace", action="update", status=1),
        RBACPermission(name="删除命名空间", code="namespace:delete", permission_type="api", resource_type="namespace", action="delete", status=1),
        # 服务管理
        RBACPermission(name="服务管理", code="service:read", permission_type="api", resource_type="service", action="read", status=1),
        RBACPermission(name="创建服务", code="service:create", permission_type="api", resource_type="service", action="create", status=1),
        RBACPermission(name="编辑服务", code="service:update", permission_type="api", resource_type="service", action="update", status=1),
        RBACPermission(name="删除服务", code="service:delete", permission_type="api", resource_type="service", action="delete", status=1),
        RBACPermission(name="部署服务", code="service:deploy", permission_type="api", resource_type="service", action="deploy", status=1),
        RBACPermission(name="服务配置", code="service:config", permission_type="api", resource_type="service", action="config", status=1),
        # 发布管理
        RBACPermission(name="发布管理", code="release:read", permission_type="api", resource_type="release", action="read", status=1),
        RBACPermission(name="创建发布", code="release:create", permission_type="api", resource_type="release", action="create", status=1),
        RBACPermission(name="执行发布", code="release:execute", permission_type="api", resource_type="release", action="execute", status=1),
        RBACPermission(name="审批发布", code="release:approve", permission_type="api", resource_type="release", action="approve", status=1),
        RBACPermission(name="回滚发布", code="release:rollback", permission_type="api", resource_type="release", action="rollback", status=1),
        # 用户管理
        RBACPermission(name="用户管理", code="user:read", permission_type="api", resource_type="user", action="read", status=1),
        RBACPermission(name="用户管理", code="user:manage", permission_type="api", resource_type="user", action="manage", status=1),
        # 角色管理
        RBACPermission(name="角色管理", code="role:read", permission_type="api", resource_type="role", action="read", status=1),
        RBACPermission(name="角色管理", code="role:manage", permission_type="api", resource_type="role", action="manage", status=1),
    ]
    
    for perm in permissions:
        db.add(perm)
    await db.commit()
    print(f"✅ 权限数据初始化完成: {len(permissions)} 个")


async def create_test_data(db: AsyncSession):
    """创建测试数据"""
    # 创建集群
    cluster = Cluster(
        name="fushang",
        display_name="富尚集群",
        api_server="https://kubernetes.default.svc",
        status=1,
        description="生产环境集群"
    )
    db.add(cluster)
    await db.commit()
    await db.refresh(cluster)
    print(f"✅ 集群创建完成: {cluster.name}")
    
    # 创建命名空间
    namespaces = [
        Namespace(cluster_id=cluster.id, name="tczxc-prod-a", display_name="生产环境A", env_type=EnvType.PROD, status=1),
        Namespace(cluster_id=cluster.id, name="tczxc-prod-b", display_name="生产环境B", env_type=EnvType.PROD, status=1),
        Namespace(cluster_id=cluster.id, name="tczxc-test", display_name="测试环境", env_type=EnvType.TEST, status=1),
        Namespace(cluster_id=cluster.id, name="tczxc-dev", display_name="开发环境", env_type=EnvType.DEV, status=1),
    ]
    for ns in namespaces:
        db.add(ns)
    await db.commit()
    print(f"✅ 命名空间创建完成: {len(namespaces)} 个")
    
    # 创建服务
    services = [
        Service(
            namespace_id=1, name="user-service", display_name="用户服务",
            type=ServiceType.DEPLOYMENT, deploy_name="user-service",
            container_name="user-service", harbor_project="tczxc", harbor_repo="user-service",
            port=8080, replicas=3, status=1
        ),
        Service(
            namespace_id=1, name="order-service", display_name="订单服务",
            type=ServiceType.DEPLOYMENT, deploy_name="order-service",
            container_name="order-service", harbor_project="tczxc", harbor_repo="order-service",
            port=8080, replicas=3, status=1
        ),
        Service(
            namespace_id=1, name="payment-service", display_name="支付服务",
            type=ServiceType.DEPLOYMENT, deploy_name="payment-service",
            container_name="payment-service", harbor_project="tczxc", harbor_repo="payment-service",
            port=8080, replicas=2, status=1
        ),
        Service(
            namespace_id=3, name="test-app", display_name="测试应用",
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
