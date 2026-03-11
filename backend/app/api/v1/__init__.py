from fastapi import APIRouter
from app.api.v1 import auth, clusters, releases, services, users, harbor

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(clusters.router, prefix="/clusters", tags=["集群管理"])
api_router.include_router(services.router, prefix="/services", tags=["服务管理"])
api_router.include_router(releases.router, prefix="/releases", tags=["发布管理"])
api_router.include_router(users.router, prefix="/users", tags=["人员管理"])
api_router.include_router(harbor.router, prefix="/harbor", tags=["Harbor 镜像仓库"])
