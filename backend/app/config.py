from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "K8s Release Platform"
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # 数据库配置
    DATABASE_URL: str = "mysql+aiomysql://root:rootpass@localhost:3306/k8s_platform?charset=utf8mb4"
    
    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT 配置
    JWT_SECRET: str = "jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24小时
    
    # Harbor 配置
    HARBOR_URL: str = "https://harbor.example.com"
    HARBOR_USERNAME: Optional[str] = None
    HARBOR_PASSWORD: Optional[str] = None
    
    # K8s 配置
    K8S_DEFAULT_TIMEOUT: int = 300
    K8S_ROLLING_UPDATE_TIMEOUT: int = 600
    
    # 加密配置
    ENCRYPTION_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"


settings = Settings()
