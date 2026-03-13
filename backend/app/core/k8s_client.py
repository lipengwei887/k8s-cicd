import asyncio
import logging
import tempfile
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from kubernetes import client
from kubernetes.client.exceptions import ApiException

logger = logging.getLogger(__name__)


class K8sClientError(Exception):
    """K8s 客户端异常"""
    pass


class DeploymentUpdateError(Exception):
    """Deployment 更新异常"""
    pass


class K8sClientManager:
    """K8s 客户端管理器 - 支持多集群"""
    
    _instances: Dict[int, 'K8sClientManager'] = {}
    
    def __init__(self, cluster_id: int, api_server: str, token: str, ca_cert: Optional[str] = None, kubeconfig: Optional[str] = None):
        self.cluster_id = cluster_id
        self.api_server = api_server
        self.token = token
        self.ca_cert = ca_cert
        self.kubeconfig = kubeconfig
        self._apps_v1: Optional[client.AppsV1Api] = None
        self._core_v1: Optional[client.CoreV1Api] = None
        self._lock = asyncio.Lock()
    
    @classmethod
    async def get_client(cls, cluster_id: int, api_server: str, token: str, ca_cert: Optional[str] = None, kubeconfig: Optional[str] = None) -> 'K8sClientManager':
        """获取或创建客户端实例 (单例模式)"""
        if cluster_id not in cls._instances:
            cls._instances[cluster_id] = cls(cluster_id, api_server, token, ca_cert, kubeconfig)
            await cls._instances[cluster_id]._init_client()
        return cls._instances[cluster_id]
    
    async def _init_client(self):
        """初始化 K8s 客户端"""
        try:
            # 如果提供了 kubeconfig，使用 kubeconfig 创建客户端
            if self.kubeconfig:
                from kubernetes.config import kube_config
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    f.write(self.kubeconfig)
                    kubeconfig_path = f.name
                
                # 从 kubeconfig 加载配置
                configuration = client.Configuration()
                kube_config.load_kube_config(config_file=kubeconfig_path, client_configuration=configuration)
                # 跳过 SSL 验证（用于开发/测试环境）
                configuration.verify_ssl = False
            else:
                # 使用 token 创建客户端
                configuration = client.Configuration()
                configuration.host = self.api_server
                # 如果没有 CA 证书，跳过 SSL 验证（用于开发/测试环境）
                configuration.verify_ssl = bool(self.ca_cert)
                configuration.api_key['authorization'] = f'Bearer {self.token}'
                
                if self.ca_cert:
                    configuration.ssl_ca_cert = self._write_temp_cert(self.ca_cert)
            
            # 为每个客户端创建独立的配置
            self._apps_v1 = client.AppsV1Api(client.ApiClient(configuration))
            self._core_v1 = client.CoreV1Api(client.ApiClient(configuration))
            logger.info(f"K8s client initialized for cluster {self.cluster_id}")
        except Exception as e:
            logger.error(f"Failed to initialize K8s client: {e}")
            raise K8sClientError(f"K8s client init failed: {e}")
    
    def _write_temp_cert(self, cert_content: str) -> str:
        """将证书写入临时文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
            f.write(cert_content)
            return f.name
    
    @property
    def apps_v1(self) -> client.AppsV1Api:
        if not self._apps_v1:
            raise K8sClientError("K8s client not initialized")
        return self._apps_v1
    
    @property
    def core_v1(self) -> client.CoreV1Api:
        if not self._core_v1:
            raise K8sClientError("K8s client not initialized")
        return self._core_v1


class K8sService:
    """K8s 服务操作类"""
    
    def __init__(self, cluster_id: int, api_server: str, token: str, ca_cert: Optional[str] = None, kubeconfig: Optional[str] = None):
        self.cluster_id = cluster_id
        self.client_manager: Optional[K8sClientManager] = None
        self.api_server = api_server
        self.token = token
        self.ca_cert = ca_cert
        self.kubeconfig = kubeconfig
    
    async def _get_client(self) -> K8sClientManager:
        """获取 K8s 客户端"""
        if not self.client_manager:
            self.client_manager = await K8sClientManager.get_client(
                self.cluster_id, self.api_server, self.token, self.ca_cert, self.kubeconfig
            )
        return self.client_manager
    
    async def update_deployment_image(
        self,
        namespace: str,
        deployment_name: str,
        container_name: str,
        new_image: str,
        timeout: int = 300,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        更新 Deployment 镜像并等待滚动更新完成
        """
        client_mgr = await self._get_client()
        apps_v1 = client_mgr.apps_v1
        
        try:
            # 1. 获取当前 Deployment
            logger.info(f"Fetching deployment {deployment_name} in namespace {namespace}")
            deployment = await asyncio.to_thread(
                apps_v1.read_namespaced_deployment,
                name=deployment_name,
                namespace=namespace
            )
            
            # 2. 记录原始镜像信息
            original_image = None
            container_found = False
            for container in deployment.spec.template.spec.containers:
                if container.name == container_name:
                    original_image = container.image
                    container.image = new_image
                    container_found = True
                    break
            
            if not container_found:
                raise DeploymentUpdateError(f"Container {container_name} not found in deployment")
            
            # 3. 添加版本注解 (用于追踪)
            if deployment.spec.template.metadata.annotations is None:
                deployment.spec.template.metadata.annotations = {}
            deployment.spec.template.metadata.annotations['release-platform/version'] = new_image
            deployment.spec.template.metadata.annotations['release-platform/updated-at'] = datetime.utcnow().isoformat()
            
            # 4. 执行更新
            logger.info(f"Updating deployment image: {original_image} -> {new_image}")
            updated_deployment = await asyncio.to_thread(
                apps_v1.patch_namespaced_deployment,
                name=deployment_name,
                namespace=namespace,
                body=deployment
            )
            
            # 5. 等待滚动更新完成
            result = await self._wait_for_rolling_update(
                namespace=namespace,
                deployment_name=deployment_name,
                timeout=timeout,
                progress_callback=progress_callback
            )
            
            return {
                'success': result['success'],
                'deployment': updated_deployment.metadata.name,
                'namespace': namespace,
                'original_image': original_image,
                'new_image': new_image,
                'replicas': updated_deployment.spec.replicas,
                'ready_replicas': result.get('ready_replicas', 0),
                'message': result.get('message', ''),
                'duration': result.get('duration', 0)
            }
            
        except ApiException as e:
            logger.error(f"K8s API error: {e.status} - {e.reason}")
            if e.status == 404:
                raise DeploymentUpdateError(f"Deployment {deployment_name} not found in namespace {namespace}")
            elif e.status == 403:
                raise DeploymentUpdateError(f"Permission denied: {e.reason}")
            else:
                raise DeploymentUpdateError(f"K8s API error: {e.reason}")
        except asyncio.TimeoutError:
            raise DeploymentUpdateError(f"Rolling update timeout after {timeout}s")
        except Exception as e:
            logger.error(f"Unexpected error during deployment update: {e}")
            raise DeploymentUpdateError(f"Update failed: {str(e)}")
    
    async def _wait_for_rolling_update(
        self,
        namespace: str,
        deployment_name: str,
        timeout: int,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """等待滚动更新完成，包含 Pod 状态检查和失败检测"""
        client_mgr = await self._get_client()
        apps_v1 = client_mgr.apps_v1
        core_v1 = client_mgr.core_v1
        
        start_time = asyncio.get_event_loop().time()
        check_interval = 3  # 检查间隔(秒)
        consecutive_failures = 0  # 连续失败计数
        max_consecutive_failures = 3  # 最大连续失败次数
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                # 超时前获取 Pod 日志
                logs = await self._get_failed_pods_logs(namespace, deployment_name)
                raise asyncio.TimeoutError(f"Rolling update timeout. Pod logs: {logs}")
            
            try:
                # 获取 Deployment 状态
                deployment = await asyncio.to_thread(
                    apps_v1.read_namespaced_deployment_status,
                    name=deployment_name,
                    namespace=namespace
                )
                
                status = deployment.status
                spec = deployment.spec
                
                # 计算进度
                desired = spec.replicas or 0
                updated = status.updated_replicas or 0
                ready = status.ready_replicas or 0
                available = status.available_replicas or 0
                unavailable = status.unavailable_replicas or 0
                
                # 获取 Pod 详细状态
                pod_status = await self._get_pods_status(namespace, deployment_name)
                
                progress = {
                    'desired': desired,
                    'updated': updated,
                    'ready': ready,
                    'available': available,
                    'unavailable': unavailable,
                    'progress_percent': (ready / desired * 100) if desired > 0 else 0,
                    'elapsed_seconds': int(elapsed),
                    'status': 'updating',
                    'pods': pod_status
                }
                
                # 检查是否有 Pod 启动失败
                failed_pods = [p for p in pod_status if p.get('status') in ['CrashLoopBackOff', 'ImagePullBackOff', 'ErrImagePull', 'Error']]
                if failed_pods:
                    # 获取失败 Pod 的日志
                    logs = await self._get_failed_pods_logs(namespace, deployment_name, failed_pods)
                    progress['status'] = 'failed'
                    progress['message'] = f"Pod start failed: {failed_pods[0].get('status')}"
                    progress['failed_pods'] = failed_pods
                    progress['logs'] = logs
                    if progress_callback:
                        await asyncio.to_thread(progress_callback, progress)
                    return {
                        'success': False,
                        'message': f"Rolling update failed: {failed_pods[0].get('status')}. Logs: {logs[:500]}",
                        'ready_replicas': ready,
                        'duration': int(elapsed),
                        'failed_pods': failed_pods,
                        'logs': logs
                    }
                
                # 检查更新条件
                conditions = status.conditions or []
                progressing = next(
                    (c for c in conditions if c.type == 'Progressing'),
                    None
                )
                
                if progressing and progressing.reason == 'ProgressDeadlineExceeded':
                    logs = await self._get_failed_pods_logs(namespace, deployment_name)
                    progress['status'] = 'failed'
                    progress['message'] = 'Progress deadline exceeded'
                    progress['logs'] = logs
                    if progress_callback:
                        await asyncio.to_thread(progress_callback, progress)
                    return {
                        'success': False,
                        'message': f"Rolling update failed: progress deadline exceeded. Logs: {logs[:500]}",
                        'ready_replicas': ready,
                        'duration': int(elapsed),
                        'logs': logs
                    }
                
                # 检查是否完成：所有 Pod 都 ready 且可用
                if updated == desired and ready == desired and available == desired and ready > 0:
                    progress['status'] = 'completed'
                    if progress_callback:
                        await asyncio.to_thread(progress_callback, progress)
                    
                    # 获取成功的 Pod 日志（最后几条）
                    logs = await self._get_pods_logs(namespace, deployment_name, tail_lines=50)
                    
                    return {
                        'success': True,
                        'message': 'Rolling update completed successfully',
                        'ready_replicas': ready,
                        'duration': int(elapsed),
                        'pod_status': pod_status,
                        'logs': logs
                    }
                
                # 如果 updated == desired 但 ready < desired，说明 Pod 启动有问题
                if updated == desired and ready < desired and elapsed > 30:
                    # 等待30秒后检查是否有 Pod 问题
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logs = await self._get_failed_pods_logs(namespace, deployment_name)
                        progress['status'] = 'failed'
                        progress['message'] = f'Pods not ready after {int(elapsed)}s'
                        progress['logs'] = logs
                        if progress_callback:
                            await asyncio.to_thread(progress_callback, progress)
                        return {
                            'success': False,
                            'message': f"Rolling update failed: Pods not ready after {int(elapsed)}s. Logs: {logs[:500]}",
                            'ready_replicas': ready,
                            'duration': int(elapsed),
                            'logs': logs
                        }
                else:
                    consecutive_failures = 0
                
                # 回调进度
                if progress_callback:
                    await asyncio.to_thread(progress_callback, progress)
                
                logger.debug(f"Rolling update progress: {ready}/{desired} ready")
                
            except ApiException as e:
                logger.error(f"Error checking deployment status: {e}")
                raise
            
            await asyncio.sleep(check_interval)
    
    async def get_deployment_status(
        self,
        namespace: str,
        deployment_name: str
    ) -> Dict[str, Any]:
        """获取 Deployment 状态"""
        client_mgr = await self._get_client()
        apps_v1 = client_mgr.apps_v1
        core_v1 = client_mgr.core_v1
        
        try:
            # 获取 Deployment
            deployment = await asyncio.to_thread(
                apps_v1.read_namespaced_deployment,
                name=deployment_name,
                namespace=namespace
            )
            
            # 获取 Pod 列表
            selector = deployment.spec.selector.match_labels
            label_selector = ','.join([f"{k}={v}" for k, v in selector.items()])
            
            pods = await asyncio.to_thread(
                core_v1.list_namespaced_pod,
                namespace=namespace,
                label_selector=label_selector
            )
            
            pod_list = []
            for pod in pods.items:
                container_statuses = pod.status.container_statuses or []
                ready_count = sum(1 for c in container_statuses if c.ready)
                restart_count = sum(c.restart_count for c in container_statuses)
                
                pod_list.append({
                    'name': pod.metadata.name,
                    'status': pod.status.phase,
                    'ready': f"{ready_count}/{len(container_statuses)}",
                    'restarts': restart_count,
                    'age': pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None,
                    'node': pod.spec.node_name
                })
            
            return {
                'name': deployment.metadata.name,
                'namespace': namespace,
                'replicas': deployment.spec.replicas,
                'ready_replicas': deployment.status.ready_replicas or 0,
                'updated_replicas': deployment.status.updated_replicas or 0,
                'available_replicas': deployment.status.available_replicas or 0,
                'strategy': deployment.spec.strategy.type if deployment.spec.strategy else 'RollingUpdate',
                'pods': pod_list,
                'conditions': [
                    {
                        'type': c.type,
                        'status': c.status,
                        'reason': c.reason,
                        'message': c.message
                    }
                    for c in (deployment.status.conditions or [])
                ]
            }
            
        except ApiException as e:
            logger.error(f"Failed to get deployment status: {e}")
            raise K8sClientError(f"Failed to get status: {e.reason}")
    
    async def _get_pods_status(self, namespace: str, deployment_name: str) -> list:
        """获取 Deployment 关联的 Pod 状态列表"""
        try:
            client_mgr = await self._get_client()
            apps_v1 = client_mgr.apps_v1
            core_v1 = client_mgr.core_v1
            
            # 获取 Deployment
            deployment = await asyncio.to_thread(
                apps_v1.read_namespaced_deployment,
                name=deployment_name,
                namespace=namespace
            )
            
            # 获取 Pod 列表
            selector = deployment.spec.selector.match_labels
            label_selector = ','.join([f"{k}={v}" for k, v in selector.items()])
            
            pods = await asyncio.to_thread(
                core_v1.list_namespaced_pod,
                namespace=namespace,
                label_selector=label_selector
            )
            
            pod_status_list = []
            for pod in pods.items:
                # 获取容器状态
                container_statuses = pod.status.container_statuses or []
                
                # 检查是否有等待状态的容器（如 ImagePullBackOff）
                waiting_reason = None
                for cs in container_statuses:
                    if cs.state and cs.state.waiting:
                        waiting_reason = cs.state.waiting.reason
                        break
                    if cs.state and cs.state.terminated and cs.state.terminated.exit_code != 0:
                        waiting_reason = f"Error (exit {cs.state.terminated.exit_code})"
                
                # 确定 Pod 状态
                if waiting_reason:
                    status = waiting_reason
                elif pod.status.phase == 'Running' and all(cs.ready for cs in container_statuses):
                    status = 'Running'
                else:
                    status = pod.status.phase
                
                pod_status_list.append({
                    'name': pod.metadata.name,
                    'status': status,
                    'phase': pod.status.phase,
                    'ready': all(cs.ready for cs in container_statuses) if container_statuses else False,
                    'restarts': sum(cs.restart_count for cs in container_statuses),
                    'age': pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None
                })
            
            return pod_status_list
            
        except Exception as e:
            logger.error(f"Failed to get pods status: {e}")
            return []
    
    async def _get_pods_logs(self, namespace: str, deployment_name: str, tail_lines: int = 50) -> str:
        """获取 Pod 的日志（用于成功的发布）"""
        try:
            client_mgr = await self._get_client()
            apps_v1 = client_mgr.apps_v1
            core_v1 = client_mgr.core_v1
            
            # 获取 Deployment
            deployment = await asyncio.to_thread(
                apps_v1.read_namespaced_deployment,
                name=deployment_name,
                namespace=namespace
            )
            
            # 获取 Pod 列表
            selector = deployment.spec.selector.match_labels
            label_selector = ','.join([f"{k}={v}" for k, v in selector.items()])
            
            pods = await asyncio.to_thread(
                core_v1.list_namespaced_pod,
                namespace=namespace,
                label_selector=label_selector
            )
            
            logs = []
            for pod in pods.items[:3]:  # 最多获取3个 Pod 的日志
                try:
                    pod_logs = await asyncio.to_thread(
                        core_v1.read_namespaced_pod_log,
                        name=pod.metadata.name,
                        namespace=namespace,
                        tail_lines=tail_lines
                    )
                    logs.append(f"=== {pod.metadata.name} ===\n{pod_logs}")
                except Exception as e:
                    logs.append(f"=== {pod.metadata.name} ===\nFailed to get logs: {str(e)}")
            
            return '\n\n'.join(logs)
            
        except Exception as e:
            logger.error(f"Failed to get pods logs: {e}")
            return f"Failed to get logs: {str(e)}"
    
    async def _get_failed_pods_logs(self, namespace: str, deployment_name: str, failed_pods: list = None) -> str:
        """获取失败 Pod 的日志"""
        # 复用 _get_pods_logs 方法
        return await self._get_pods_logs(namespace, deployment_name, tail_lines=100)
