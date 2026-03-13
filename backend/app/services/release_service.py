import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.release import ReleaseRecord, ReleaseStatus
from app.models.service import Service
from app.models.cluster import Cluster
from app.models.namespace import Namespace
from app.core.k8s_client import K8sService, DeploymentUpdateError
from app.core.security import secret_manager

logger = logging.getLogger(__name__)


class ReleaseService:
    """发布服务 - 处理完整的发布流程"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._active_releases: Dict[int, asyncio.Task] = {}
    
    async def create_release(
        self,
        service_id: int,
        operator_id: int,
        image_tag: str,
        require_approval: bool = False,
        validity_period: int = 0,
        parent_release_id: Optional[int] = None
    ) -> ReleaseRecord:
        """创建发布单
        
        Args:
            service_id: 服务ID
            operator_id: 操作人ID
            image_tag: 镜像标签
            require_approval: 是否需要审批
            validity_period: 时效时长（小时），0 表示不限制
            parent_release_id: 父发布单ID（时效内重复执行时使用）
        """
        # 获取服务信息
        result = await self.db.execute(
            select(Service).where(Service.id == service_id)
        )
        service = result.scalar_one_or_none()
        if not service:
            raise ValueError(f"Service {service_id} not found")
        
        # 获取当前运行的镜像
        current_image = await self._get_current_image(service)
        
        # 构建完整镜像路径
        image_full_path = self._build_image_path(service, image_tag)
        
        # 确定发布状态
        # 如果是时效内重复执行，直接设置为 pending（免审批）
        is_repeated = parent_release_id is not None
        if is_repeated:
            status = ReleaseStatus.PENDING
        else:
            status = ReleaseStatus.PENDING if not require_approval else ReleaseStatus.APPROVING
        
        # 计算时效时间
        validity_start_at = None
        validity_end_at = None
        if validity_period > 0:
            validity_start_at = datetime.utcnow()
            validity_end_at = validity_start_at + timedelta(hours=validity_period)
        
        # 创建发布记录
        release = ReleaseRecord(
            service_id=service_id,
            operator_id=operator_id,
            image_tag=image_tag,
            image_full_path=image_full_path,
            previous_image=current_image,
            status=status,
            message='Waiting for execution',
            validity_period=validity_period,
            validity_start_at=validity_start_at,
            validity_end_at=validity_end_at,
            parent_release_id=parent_release_id,
            is_repeated=1 if is_repeated else 0
        )
        
        self.db.add(release)
        await self.db.commit()
        await self.db.refresh(release)
        
        logger.info(f"Release created: {release.id} for service {service.name}, validity_period={validity_period}h, is_repeated={is_repeated}")
        
        return release
    
    async def check_validity_for_reexecution(
        self,
        parent_release_id: int,
        operator_id: int
    ) -> Optional[ReleaseRecord]:
        """检查是否可以在时效内免审批重新执行发布
        
        Args:
            parent_release_id: 父发布单ID
            operator_id: 操作人ID
            
        Returns:
            如果可以在时效内执行，返回父发布单记录，否则返回 None
        """
        result = await self.db.execute(
            select(ReleaseRecord).where(ReleaseRecord.id == parent_release_id)
        )
        parent_release = result.scalar_one_or_none()
        
        if not parent_release:
            return None
        
        # 检查是否是同一用户
        if parent_release.operator_id != operator_id:
            return None
        
        # 检查时效
        if not parent_release.can_execute_without_approval():
            return None
        
        return parent_release
    
    async def execute_release(
        self,
        release_id: int,
        operator_id: int
    ) -> Dict[str, Any]:
        """执行发布"""
        result = await self.db.execute(
            select(ReleaseRecord).where(ReleaseRecord.id == release_id)
        )
        release = result.scalar_one_or_none()
        if not release:
            raise ValueError(f"Release {release_id} not found")
        
        if release.status not in [ReleaseStatus.PENDING, ReleaseStatus.APPROVING]:
            raise ValueError(f"Cannot execute release with status: {release.status}")
        
        # 获取服务和集群信息
        service_result = await self.db.execute(
            select(Service).where(Service.id == release.service_id)
        )
        service = service_result.scalar_one()
        
        ns_result = await self.db.execute(
            select(Namespace).where(Namespace.id == service.namespace_id)
        )
        namespace = ns_result.scalar_one()
        
        cluster_result = await self.db.execute(
            select(Cluster).where(Cluster.id == namespace.cluster_id)
        )
        cluster = cluster_result.scalar_one()
        
        # 解密 kubeconfig 或 token
        kubeconfig = secret_manager.decrypt(cluster.kubeconfig_encrypted) if cluster.kubeconfig_encrypted else None
        token = secret_manager.decrypt(cluster.sa_token_encrypted) if cluster.sa_token_encrypted else ""
        
        # 更新状态为运行中
        release.status = ReleaseStatus.RUNNING
        release.started_at = datetime.utcnow()
        await self.db.commit()
        
        try:
            # 创建 K8s 服务（优先使用 kubeconfig）
            k8s_service = K8sService(
                cluster_id=cluster.id,
                api_server=cluster.api_server,
                token=token,
                ca_cert=cluster.ca_cert,
                kubeconfig=kubeconfig
            )
            
            # 定义进度回调
            async def progress_callback(progress: Dict[str, Any]):
                release.pod_status = json.dumps(progress)
                await self.db.commit()
            
            # 执行更新
            result = await k8s_service.update_deployment_image(
                namespace=namespace.name,
                deployment_name=service.deploy_name,
                container_name=service.container_name or service.deploy_name,
                new_image=release.image_full_path,
                timeout=600,
                progress_callback=progress_callback
            )
            
            # 更新发布记录
            release.status = ReleaseStatus.SUCCESS if result['success'] else ReleaseStatus.FAILED
            release.message = result['message']
            release.pod_status = json.dumps(result.get('pod_status', [])) if result.get('pod_status') else None
            release.logs = result.get('logs', '')  # 保存 Pod 日志
            release.completed_at = datetime.utcnow()
            await self.db.commit()
            
            return {
                'success': result['success'],
                'release_id': release.id,
                'message': result['message'],
                'duration': result['duration']
            }
            
        except DeploymentUpdateError as e:
            release.status = ReleaseStatus.FAILED
            release.message = str(e)
            # 尝试从异常信息中提取日志
            if hasattr(e, 'logs'):
                release.logs = e.logs
            release.completed_at = datetime.utcnow()
            await self.db.commit()
            
            logger.error(f"Release {release_id} failed: {e}")
            raise
        except Exception as e:
            release.status = ReleaseStatus.FAILED
            release.message = f"Unexpected error: {str(e)}"
            release.completed_at = datetime.utcnow()
            await self.db.commit()
            
            logger.error(f"Release {release_id} failed with unexpected error: {e}")
            raise
    
    async def rollback_release(
        self,
        release_id: int,
        operator_id: int
    ) -> Dict[str, Any]:
        """回滚到指定发布版本"""
        result = await self.db.execute(
            select(ReleaseRecord).where(ReleaseRecord.id == release_id)
        )
        release = result.scalar_one_or_none()
        if not release:
            raise ValueError(f"Release {release_id} not found")
        
        if not release.previous_image:
            raise ValueError("No previous image available for rollback")
        
        # 获取服务和集群信息
        service_result = await self.db.execute(
            select(Service).where(Service.id == release.service_id)
        )
        service = service_result.scalar_one()
        
        ns_result = await self.db.execute(
            select(Namespace).where(Namespace.id == service.namespace_id)
        )
        namespace = ns_result.scalar_one()
        
        cluster_result = await self.db.execute(
            select(Cluster).where(Cluster.id == namespace.cluster_id)
        )
        cluster = cluster_result.scalar_one()
        
        token = secret_manager.decrypt(cluster.sa_token_encrypted) if cluster.sa_token_encrypted else ""
        
        # 创建回滚记录
        rollback_release = ReleaseRecord(
            service_id=release.service_id,
            operator_id=operator_id,
            image_tag=release.previous_image.split(':')[-1],
            image_full_path=release.previous_image,
            previous_image=release.image_full_path,
            status=ReleaseStatus.RUNNING,
            rollback_to=release.id,
            started_at=datetime.utcnow()
        )
        self.db.add(rollback_release)
        await self.db.commit()
        await self.db.refresh(rollback_release)
        
        try:
            k8s_service = K8sService(
                cluster_id=cluster.id,
                api_server=cluster.api_server,
                token=token,
                ca_cert=cluster.ca_cert
            )
            
            result = await k8s_service.update_deployment_image(
                namespace=namespace.name,
                deployment_name=service.deploy_name,
                container_name=service.container_name or service.deploy_name,
                new_image=release.previous_image,
                timeout=600
            )
            
            rollback_release.status = ReleaseStatus.SUCCESS if result['success'] else ReleaseStatus.FAILED
            rollback_release.message = f"Rollback: {result['message']}"
            rollback_release.completed_at = datetime.utcnow()
            
            # 更新原发布记录状态
            release.status = ReleaseStatus.ROLLED_BACK
            await self.db.commit()
            
            return {
                'success': result['success'],
                'rollback_release_id': rollback_release.id,
                'message': result['message']
            }
            
        except Exception as e:
            rollback_release.status = ReleaseStatus.FAILED
            rollback_release.message = f"Rollback failed: {str(e)}"
            rollback_release.completed_at = datetime.utcnow()
            await self.db.commit()
            raise
    
    def _build_image_path(self, service: Service, image_tag: str) -> str:
        """构建完整镜像路径"""
        # 从 current_image 解析 harbor host，如果没有则使用默认值
        if service.current_image:
            # 解析镜像地址，提取 harbor host
            from app.services.harbor_service import harbor_service
            harbor_host, project, repo = harbor_service.parse_image_url(service.current_image)
            if harbor_host:
                return f"{harbor_host}/{project}/{repo}:{image_tag}"
        
        # 回退到使用服务配置
        project = service.harbor_project or 'library'
        repo = service.harbor_repo or service.name
        return f"{project}/{repo}:{image_tag}"
    
    async def _get_current_image(self, service: Service) -> Optional[str]:
        """获取服务当前运行的镜像"""
        # 优先使用数据库中保存的 current_image
        if service.current_image:
            return service.current_image
        
        # 如果数据库中没有，尝试从 K8s 集群获取（可选）
        try:
            ns_result = await self.db.execute(
                select(Namespace).where(Namespace.id == service.namespace_id)
            )
            namespace = ns_result.scalar_one()
            
            cluster_result = await self.db.execute(
                select(Cluster).where(Cluster.id == namespace.cluster_id)
            )
            cluster = cluster_result.scalar_one()
            
            # 如果没有 kubeconfig，直接返回 None
            if not cluster.kubeconfig_encrypted:
                return None
            
            # 从 K8s 获取当前镜像（这里简化处理，实际应该调用 K8s API）
            # 由于 SSL 证书问题，暂时跳过实时获取
            logger.info(f"Using current_image from database for service {service.name}")
            return service.current_image
            
        except Exception as e:
            logger.warning(f"Failed to get current image from K8s: {e}")
            return service.current_image
