"""
Harbor 镜像仓库 API
提供获取镜像标签等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import logging
import requests

from app.api.v1.auth import get_current_active_user
from app.models.user import User
from app.services.harbor_service import HarborService, harbor_service
from app.services.k8s_sync_service import K8sSyncService
from app.core.security import secret_manager
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.service import Service
from app.models.namespace import Namespace
from app.models.cluster import Cluster

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/tags")
async def get_image_tags(
    project: str = Query(..., description="Harbor 项目名称"),
    repository: str = Query(..., description="仓库名称"),
    limit: int = Query(50, ge=1, le=100, description="返回数量限制"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取 Harbor 镜像的标签列表
    
    Args:
        project: Harbor 项目名称
        repository: 仓库名称
        limit: 返回数量限制
        
    Returns:
        标签列表
    """
    try:
        tags = harbor_service.get_image_tags_simple(project, repository, limit)
        return {"items": tags, "total": len(tags)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get image tags: {str(e)}")


@router.get("/service/{service_id}/tags")
async def get_service_image_tags(
    service_id: int,
    limit: int = Query(50, ge=1, le=100, description="返回数量限制"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    根据服务 ID 获取该服务对应镜像的标签列表
    优先从 K8s 实时获取当前镜像，如果没有则从数据库获取
    自动从服务的 current_image 中提取 harbor 地址和项目信息
    优先尝试从 K8s Secret 获取 Harbor 认证信息
    
    Args:
        service_id: 服务 ID
        limit: 返回数量限制
        
    Returns:
        标签列表和当前使用的镜像信息
    """
    # 获取服务信息
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # 获取服务的集群信息
    namespace_result = await db.execute(
        select(Namespace).where(Namespace.id == service.namespace_id)
    )
    namespace = namespace_result.scalar_one_or_none()
    
    harbor_credentials = None
    current_image = None
    image_source = "database"  # 记录镜像来源
    
    # 尝试从 K8s 实时获取当前镜像
    if namespace:
        cluster_result = await db.execute(
            select(Cluster).where(Cluster.id == namespace.cluster_id)
        )
        cluster = cluster_result.scalar_one_or_none()
        
        if cluster and cluster.kubeconfig_encrypted:
            try:
                kubeconfig = secret_manager.decrypt(cluster.kubeconfig_encrypted)
                k8s_service = K8sSyncService(kubeconfig)
                
                logger.info(f"Attempting to get image from K8s: namespace={namespace.name}, deploy_name={service.deploy_name}")
                
                # 实时从 K8s 获取当前镜像
                k8s_image = k8s_service.get_deployment_image(namespace.name, service.deploy_name)
                if k8s_image:
                    current_image = k8s_image
                    image_source = "kubernetes"
                    logger.info(f"Using real-time image from K8s for service {service_id}: {current_image}")
                else:
                    logger.warning(f"K8s returned empty image for {namespace.name}/{service.deploy_name}")
                
                # 尝试从 K8s Secret 获取 Harbor 认证信息
                harbor_credentials = k8s_service.find_harbor_secret(namespace.name)
                if not harbor_credentials:
                    harbor_credentials = k8s_service.find_harbor_secret("default")
                    
                if harbor_credentials:
                    logger.info(f"Found Harbor credentials from K8s secret for service {service_id}")
            except Exception as e:
                logger.warning(f"Failed to get info from K8s: {e}")
                logger.exception(e)
        else:
            if not cluster:
                logger.warning(f"No cluster found for namespace {namespace.id}")
            elif not cluster.kubeconfig_encrypted:
                logger.warning(f"Cluster {cluster.id} has no kubeconfig")
    
    # 如果无法从 K8s 获取，使用数据库中的 current_image
    if not current_image:
        current_image = service.current_image
        if not current_image:
            raise HTTPException(
                status_code=400, 
                detail="Service does not have current_image configured"
            )
        logger.info(f"Using cached image from database for service {service_id}: {current_image}")
    
    try:
        # 解析镜像地址获取 harbor host
        logger.info(f"Parsing image URL for service {service_id}: {current_image}")
        harbor_host, project, repository = harbor_service.parse_image_url(current_image)
        
        logger.info(f"Parsed result - host: {harbor_host}, project: {project}, repository: {repository}")
        
        if not harbor_host or not project or not repository:
            raise HTTPException(status_code=400, detail=f"Invalid image URL format: {current_image}")
        
        # 构建 harbor URL
        harbor_url = f"https://{harbor_host}"
        
        # 创建 Harbor 服务实例，传入从 Secret 获取的认证信息
        hs = HarborService(harbor_url, credentials=harbor_credentials)
        
        # 先测试 Harbor 连接
        if not hs.test_connection():
            logger.warning(f"Harbor connection test failed for {harbor_url}, will try with config credentials")
            # 如果 K8s Secret 的认证失败，尝试使用配置文件的认证
            if harbor_credentials:
                hs = HarborService(harbor_url)
                if not hs.test_connection():
                    raise HTTPException(
                        status_code=503, 
                        detail=f"无法连接到 Harbor 服务器: {harbor_url}，请检查网络连接或 Harbor 配置"
                    )
        
        # 获取镜像标签
        tags = hs.get_image_tags(project, repository, page_size=limit)
        
        # 只返回标签名列表
        tag_names = [tag['tag'] for tag in tags if tag.get('tag')]
        
        return {
            "items": tag_names,
            "total": len(tag_names),
            "current_image": current_image,
            "image_source": image_source,
            "source": "k8s-secret" if harbor_credentials else "config",
        }
    except HTTPException:
        raise
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Harbor connection error for service {service_id}: {e}")
        raise HTTPException(
            status_code=503, 
            detail=f"无法连接到 Harbor 服务器，请检查网络连接"
        )
    except requests.exceptions.HTTPError as e:
        logger.error(f"Harbor API HTTP error for service {service_id}: {e}")
        if e.response.status_code == 401:
            raise HTTPException(
                status_code=401, 
                detail="Harbor 认证失败，请检查认证信息"
            )
        elif e.response.status_code == 404:
            logger.error(f"Harbor repository not found: project={project}, repository={repository}, host={harbor_url}")
            raise HTTPException(
                status_code=404, 
                detail=f"镜像仓库不存在: project={project}, repository={repository}。请检查镜像地址是否正确。"
            )
        else:
            raise HTTPException(
                status_code=502, 
                detail=f"Harbor API 错误: {e.response.status_code}"
            )
    except Exception as e:
        logger.error(f"Failed to get image tags for service {service_id}: {e}")
        raise HTTPException(status_code=500, detail=f"获取镜像标签失败: {str(e)}")


@router.get("/parse-image")
async def parse_image_url(
    image_url: str = Query(..., description="镜像地址"),
    current_user: User = Depends(get_current_active_user)
):
    """
    解析镜像地址，提取 harbor 项目和仓库名
    
    Args:
        image_url: 镜像地址，如 harbor.example.com/project/repo:tag
        
    Returns:
        解析结果
    """
    harbor_host, project, repository = harbor_service.parse_image_url(image_url)
    
    if not project or not repository:
        raise HTTPException(status_code=400, detail="Invalid image URL format")
    
    return {
        "harbor_host": harbor_host,
        "project": project,
        "repository": repository,
        "original_url": image_url
    }


@router.get("/projects")
async def get_harbor_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取 Harbor 项目列表
    
    Args:
        page: 页码
        page_size: 每页数量
        
    Returns:
        项目列表
    """
    try:
        projects = harbor_service.get_projects(page, page_size)
        return {"items": projects, "total": len(projects)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get projects: {str(e)}")


@router.get("/health")
async def check_harbor_health(
    current_user: User = Depends(get_current_active_user)
):
    """
    检查 Harbor 连接状态
    
    Returns:
        连接状态
    """
    is_healthy = harbor_service.test_connection()
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "url": harbor_service.base_url
    }
