from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# 创建异步引擎
# 优化连接池配置，确保稳定运行
# pool_size: 基础连接数，根据并发需求调整
# max_overflow: 最大溢出连接数
# pool_timeout: 获取连接的超时时间
# pool_recycle: 连接回收时间，防止连接过期
# 
# 连接池大小建议：
# - 小型应用（并发<10）: pool_size=5, max_overflow=5, 总连接数=10
# - 中型应用（并发10-50）: pool_size=10, max_overflow=10, 总连接数=20
# - 大型应用（并发>50）: pool_size=20, max_overflow=20, 总连接数=40
# 
# MySQL 默认最大连接数通常是 151，确保总连接数不超过数据库限制
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,          # 基础连接数：10（适合中小并发）
    max_overflow=10,       # 溢出连接数：10（高峰期额外连接）
    pool_timeout=30,       # 获取连接超时：30秒（避免频繁超时）
    pool_pre_ping=True,    # 连接前检查连接是否有效
    pool_recycle=1800,     # 30分钟回收连接（避免长时间占用）
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 声明基类
Base = declarative_base()


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
