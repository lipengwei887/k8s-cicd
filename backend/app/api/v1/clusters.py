from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import yaml

from app.database import get_db
from app.models.cluster import Cluster
from app.models.namespace import Namespace
from app.models.service import Service
from app.schemas.cluster import ClusterCreate, ClusterUpdate, ClusterResponse, ClusterListResponse
from app.api.v1.auth import get_current_active_user, require_admin
from app.models.user import User, UserRole
from app.core.security import secret_manager
from app.services.k8s_sync_service import K8sSyncService

router = APIRouter()


@router.get("", response_model=ClusterListResponse)
async def list_clusters(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取集群列表"""
    result = await db.execute(
        select(Cluster).where(Cluster.status == 1).offset(skip).limit(limit)
    )
    clusters = result.scalars().all()
    
    # 获取总数
    count_result = await db.execute(select(func.count(Cluster.id)).where(Cluster.status == 1))
    total = count_result.scalar()
    
    return {"items": clusters, "total": total}


@router.post("", response_model=ClusterResponse, status_code=status.HTTP_201_CREATED)
async def create_cluster(
    cluster: ClusterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建集群"""
    # 加密敏感信息
    sa_token_encrypted = secret_manager.encrypt(cluster.sa_token) if cluster.sa_token else None
    kubeconfig_encrypted = secret_manager.encrypt(cluster.kubeconfig) if cluster.kubeconfig else None
    
    db_cluster = Cluster(
        name=cluster.name,
        display_name=cluster.display_name,
        api_server=cluster.api_server,
        sa_token_encrypted=sa_token_encrypted,
        kubeconfig_encrypted=kubeconfig_encrypted,
        ca_cert=cluster.ca_cert,
        description=cluster.description
    )
    
    db.add(db_cluster)
    await db.commit()
    await db.refresh(db_cluster)
    
    return db_cluster


@router.get("/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取集群详情"""
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    return cluster


@router.put("/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: int,
    cluster_update: ClusterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新集群"""
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    update_data = cluster_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cluster, field, value)
    
    await db.commit()
    await db.refresh(cluster)
    
    return cluster


@router.delete("/{cluster_id}")
async def delete_cluster(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除集群"""
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    cluster.status = 0  # 软删除
    await db.commit()
    
    return {"message": "Cluster deleted successfully"}


@router.get("/{cluster_id}/namespaces")
async def get_cluster_namespaces(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取集群下的命名空间"""
    result = await db.execute(
        select(Namespace).where(Namespace.cluster_id == cluster_id, Namespace.status == 1)
    )
    namespaces = result.scalars().all()
    
    return {"items": namespaces}


@router.post("/{cluster_id}/sync", dependencies=[Depends(require_admin)])
async def sync_cluster(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    同步集群信息
    自动从集群获取命名空间和 Deployment/StatefulSet
    """
    # 获取集群信息
    result = await db.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    if not cluster.kubeconfig_encrypted:
        raise HTTPException(status_code=400, detail="Cluster has no kubeconfig")
    
    # 解密 kubeconfig
    kubeconfig = secret_manager.decrypt(cluster.kubeconfig_encrypted)
    
    try:
        # 创建同步服务
        sync_service = K8sSyncService(kubeconfig)
        
        # 测试连接
        if not sync_service.test_connection():
            raise HTTPException(status_code=400, detail="Failed to connect to cluster")
        
        # 同步命名空间
        ns_list = sync_service.sync_namespaces()
        
        synced_namespaces = []
        synced_services = []
        
        for ns_info in ns_list:
            # 检查命名空间是否已存在
            result = await db.execute(
                select(Namespace).where(
                    Namespace.cluster_id == cluster_id,
                    Namespace.name == ns_info['name']
                )
            )
            existing_ns = result.scalar_one_or_none()
            
            if existing_ns:
                # 更新现有命名空间
                existing_ns.env_type = ns_info['env_type']
                existing_ns.status = 1
                namespace_id = existing_ns.id
            else:
                # 创建新命名空间
                new_ns = Namespace(
                    cluster_id=cluster_id,
                    name=ns_info['name'],
                    display_name=ns_info['display_name'],
                    env_type=ns_info['env_type'],
                    status=1,
                    description=ns_info['description']
                )
                db.add(new_ns)
                await db.commit()
                await db.refresh(new_ns)
                namespace_id = new_ns.id
                synced_namespaces.append(ns_info['name'])
            
            # 同步 Deployment
            try:
                deployments = sync_service.sync_deployments(ns_info['name'])
                for deploy_info in deployments:
                    # 检查服务是否已存在
                    result = await db.execute(
                        select(Service).where(
                            Service.namespace_id == namespace_id,
                            Service.name == deploy_info['name']
                        )
                    )
                    existing_svc = result.scalar_one_or_none()
                    
                    if existing_svc:
                        # 更新现有服务
                        existing_svc.replicas = deploy_info['replicas']
                        existing_svc.status = 1
                        existing_svc.current_image = deploy_info.get('current_image')
                        existing_svc.harbor_project = deploy_info.get('harbor_project')
                        existing_svc.harbor_repo = deploy_info.get('harbor_repo')
                    else:
                        # 创建新服务
                        new_svc = Service(
                            namespace_id=namespace_id,
                            name=deploy_info['name'],
                            display_name=deploy_info['display_name'],
                            type=deploy_info['type'],
                            deploy_name=deploy_info['deploy_name'],
                            container_name=deploy_info['container_name'],
                            harbor_project=deploy_info.get('harbor_project'),
                            harbor_repo=deploy_info.get('harbor_repo'),
                            port=deploy_info.get('port'),
                            replicas=deploy_info['replicas'],
                            status=1,
                            description=deploy_info['description']
                        )
                        db.add(new_svc)
                        synced_services.append(f"{ns_info['name']}/{deploy_info['name']}")
            except Exception as e:
                logger.warning(f"Failed to sync deployments in namespace {ns_info['name']}: {e}")
            
            # 同步 StatefulSet
            try:
                statefulsets = sync_service.sync_statefulsets(ns_info['name'])
                for sts_info in statefulsets:
                    result = await db.execute(
                        select(Service).where(
                            Service.namespace_id == namespace_id,
                            Service.name == sts_info['name']
                        )
                    )
                    existing_svc = result.scalar_one_or_none()
                    
                    if existing_svc:
                        existing_svc.replicas = sts_info['replicas']
                        existing_svc.status = 1
                        existing_svc.current_image = sts_info.get('current_image')
                        existing_svc.harbor_project = sts_info.get('harbor_project')
                        existing_svc.harbor_repo = sts_info.get('harbor_repo')
                    else:
                        new_svc = Service(
                            namespace_id=namespace_id,
                            name=sts_info['name'],
                            display_name=sts_info['display_name'],
                            type=sts_info['type'],
                            deploy_name=sts_info['deploy_name'],
                            container_name=sts_info['container_name'],
                            harbor_project=sts_info.get('harbor_project'),
                            harbor_repo=sts_info.get('harbor_repo'),
                            current_image=sts_info.get('current_image'),
                            port=sts_info.get('port'),
                            replicas=sts_info['replicas'],
                            status=1,
                            description=sts_info['description']
                        )
                        db.add(new_svc)
                        synced_services.append(f"{ns_info['name']}/{sts_info['name']}")
            except Exception as e:
                logger.warning(f"Failed to sync statefulsets in namespace {ns_info['name']}: {e}")
        
        await db.commit()
        
        return {
            "message": "Cluster synced successfully",
            "synced_namespaces": synced_namespaces,
            "synced_services": synced_services,
            "total_namespaces": len(ns_list)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync cluster: {str(e)}")


@router.post("/upload-kubeconfig", dependencies=[Depends(require_admin)])
async def upload_kubeconfig(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    上传 kubeconfig 文件创建集群
    自动解析 kubeconfig 并同步命名空间和服务
    """
    # 解析 multipart/form-data
    form = await request.form()
    
    name = form.get('name')
    display_name = form.get('display_name')
    description = form.get('description', '')
    kubeconfig_file = form.get('kubeconfig_file')
    
    if not name or not display_name:
        raise HTTPException(status_code=422, detail="name and display_name are required")
    
    if not kubeconfig_file:
        raise HTTPException(status_code=422, detail="kubeconfig_file is required")
    
    # 读取 kubeconfig 内容
    content = await kubeconfig_file.read()
    kubeconfig_content = content.decode('utf-8')
    
    # 验证 kubeconfig 格式
    try:
        config_data = yaml.safe_load(kubeconfig_content)
        if not config_data or 'clusters' not in config_data:
            raise HTTPException(status_code=400, detail="Invalid kubeconfig format")
        
        # 获取第一个集群的 API server
        first_cluster = config_data['clusters'][0]
        api_server = first_cluster['cluster']['server']
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse kubeconfig: {str(e)}")
    
    # 测试连接
    try:
        sync_service = K8sSyncService(kubeconfig_content)
        if not sync_service.test_connection():
            raise HTTPException(status_code=400, detail="Failed to connect to cluster with provided kubeconfig")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection test failed: {str(e)}")
    
    # 加密 kubeconfig
    kubeconfig_encrypted = secret_manager.encrypt(kubeconfig_content)
    
    # 创建集群记录
    db_cluster = Cluster(
        name=name,
        display_name=display_name,
        api_server=api_server,
        kubeconfig_encrypted=kubeconfig_encrypted,
        status=1,
        description=description or ""
    )
    
    db.add(db_cluster)
    await db.commit()
    await db.refresh(db_cluster)
    
    # 自动同步集群信息
    try:
        ns_list = sync_service.sync_namespaces()
        
        for ns_info in ns_list:
            # 创建命名空间
            new_ns = Namespace(
                cluster_id=db_cluster.id,
                name=ns_info['name'],
                display_name=ns_info['display_name'],
                env_type=ns_info['env_type'],
                status=1,
                description=ns_info['description']
            )
            db.add(new_ns)
            await db.commit()
            await db.refresh(new_ns)
            
            # 同步 Deployment
            try:
                deployments = sync_service.sync_deployments(ns_info['name'])
                for deploy_info in deployments:
                    new_svc = Service(
                        namespace_id=new_ns.id,
                        name=deploy_info['name'],
                        display_name=deploy_info['display_name'],
                        type=deploy_info['type'],
                        deploy_name=deploy_info['deploy_name'],
                        container_name=deploy_info['container_name'],
                        harbor_project=deploy_info.get('harbor_project'),
                        harbor_repo=deploy_info.get('harbor_repo'),
                        current_image=deploy_info.get('current_image'),  # 保存当前镜像
                        port=deploy_info.get('port'),
                        replicas=deploy_info['replicas'],
                        status=1,
                        description=deploy_info['description']
                    )
                    db.add(new_svc)
            except Exception as e:
                logger.warning(f"Failed to sync deployments: {e}")
            
            # 同步 StatefulSet
            try:
                statefulsets = sync_service.sync_statefulsets(ns_info['name'])
                for sts_info in statefulsets:
                    new_svc = Service(
                        namespace_id=new_ns.id,
                        name=sts_info['name'],
                        display_name=sts_info['display_name'],
                        type=sts_info['type'],
                        deploy_name=sts_info['deploy_name'],
                        current_image=sts_info.get('current_image'),  # 保存当前镜像
                        container_name=sts_info['container_name'],
                        harbor_project=sts_info.get('harbor_project'),
                        harbor_repo=sts_info.get('harbor_repo'),
                        port=sts_info.get('port'),
                        replicas=sts_info['replicas'],
                        status=1,
                        description=sts_info['description']
                    )
                    db.add(new_svc)
            except Exception as e:
                logger.warning(f"Failed to sync statefulsets: {e}")
        
        await db.commit()
        
    except Exception as e:
        logger.error(f"Failed to auto-sync cluster: {e}")
    
    return db_cluster


# 添加 logger 导入
import logging
logger = logging.getLogger(__name__)
