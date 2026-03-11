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
from app.core.security import get_password_hash


async def init_database():
    """初始化数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表创建完成")


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


async def main():
    """主函数"""
    print("🚀 开始初始化数据库...")
    
    # 创建表
    await init_database()
    
    # 创建数据
    async with AsyncSessionLocal() as db:
        try:
            await create_admin_user(db)
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
