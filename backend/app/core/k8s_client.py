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
            
            # 记录 patch 前的 generation，用于后续判断 K8s 是否已收到更新
            expected_generation = (updated_deployment.metadata.generation or 0)
            logger.info(f"Deployment patched, expected generation={expected_generation}")
            
            # 等待 2 秒让 K8s 开始处理滚动更新，避免第一次轮询时旧状态误判为成功
            await asyncio.sleep(2)
            
            # 5. 等待滚动更新完成
            result = await self._wait_for_rolling_update(
                namespace=namespace,
                deployment_name=deployment_name,
                timeout=timeout,
                expected_generation=expected_generation,
                progress_callback=progress_callback,
                new_image=new_image
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
        expected_generation: int = 0,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        new_image: str = None
    ) -> Dict[str, Any]:
        """等待滚动更新完成，包含 Pod 状态检查和失败检测"""
        client_mgr = await self._get_client()
        apps_v1 = client_mgr.apps_v1
        core_v1 = client_mgr.core_v1
        
        start_time = asyncio.get_event_loop().time()
        check_interval = 3  # 检查间隔(秒)
        consecutive_failures = 0  # 连续失败计数
        max_consecutive_failures = 3  # 最大连续失败次数
        min_wait_seconds = 5  # 最少等待5秒才允许判断成功，防止旧状态误判
        
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
                
                # 获取 Pod 详细状态（传入 new_image 过滤老版本 Pod）
                pod_status = await self._get_pods_status(namespace, deployment_name, new_image)
                
                # 打印 Pod 状态日志
                logger.info(f"[K8sClient] Pod status check: elapsed={elapsed:.1f}s, pods={[(p['name'], p['status'], p['ready']) for p in pod_status]}")
                
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
                
                # 检查是否有 Pod 启动失败（CrashLoopBackOff / ImagePullBackOff 等）
                failed_pods = [p for p in pod_status if p.get('status') in ['CrashLoopBackOff', 'ImagePullBackOff', 'ErrImagePull', 'Error', 'OOMKilled']]
                if failed_pods:
                    failure_reason = await self._get_failure_reason(namespace, deployment_name)
                    logs = await self._get_failed_pods_logs(namespace, deployment_name, failed_pods)
                    progress['status'] = 'failed'
                    progress['message'] = failure_reason
                    progress['failed_pods'] = failed_pods
                    progress['logs'] = logs
                    if progress_callback:
                        await progress_callback(progress)
                    return {
                        'success': False,
                        'message': failure_reason,
                        'ready_replicas': ready,
                        'duration': int(elapsed),
                        'failed_pods': failed_pods,
                        'logs': logs
                    }
                
                # 检查 Deployment conditions
                conditions = status.conditions or []
                progressing = next(
                    (c for c in conditions if c.type == 'Progressing'),
                    None
                )
                
                if progressing and progressing.reason == 'ProgressDeadlineExceeded':
                    failure_reason = await self._get_failure_reason(namespace, deployment_name)
                    logs = await self._get_failed_pods_logs(namespace, deployment_name)
                    progress['status'] = 'failed'
                    progress['message'] = failure_reason or 'Progress deadline exceeded'
                    progress['logs'] = logs
                    if progress_callback:
                        await progress_callback(progress)
                    return {
                        'success': False,
                        'message': failure_reason or 'Rolling update failed: progress deadline exceeded',
                        'ready_replicas': ready,
                        'duration': int(elapsed),
                        'logs': logs
                    }
                
                # 成功判定：必须有 Pod 且所有 Pod 都 Running+Ready 才算成功
                # 同时要求 observedGeneration >= expected_generation，确认 K8s 已处理此次更新
                # 且至少等待 min_wait_seconds 秒，防止旧 Pod 还未被替换就误判成功
                has_pods = len(pod_status) > 0
                all_pods_running = has_pods and all(
                    p.get('status') == 'Running' and p.get('ready') is True
                    for p in pod_status
                )
                observed_generation = status.observed_generation or 0
                generation_ok = (expected_generation == 0) or (observed_generation >= expected_generation)
                time_ok = elapsed >= min_wait_seconds
                if updated == desired and ready == desired and available == desired and ready > 0 and all_pods_running and generation_ok and time_ok:
                    progress['status'] = 'completed'
                    if progress_callback:
                        await progress_callback(progress)
                    
                    logs = await self._get_pods_logs(namespace, deployment_name, tail_lines=50)
                    
                    return {
                        'success': True,
                        'message': '滚动更新成功完成，所有 Pod 均已 Running',
                        'ready_replicas': ready,
                        'duration': int(elapsed),
                        'pod_status': pod_status,
                        'logs': logs
                    }
                
                # updated == desired 但 ready < desired，Pod 启动慢或有问题
                if updated == desired and ready < desired and elapsed > 30:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        failure_reason = await self._get_failure_reason(namespace, deployment_name)
                        logs = await self._get_failed_pods_logs(namespace, deployment_name)
                        progress['status'] = 'failed'
                        progress['message'] = failure_reason or f'Pods not ready after {int(elapsed)}s'
                        progress['logs'] = logs
                        if progress_callback:
                            await progress_callback(progress)
                        return {
                            'success': False,
                            'message': failure_reason or f'Rolling update failed: Pods not ready after {int(elapsed)}s',
                            'ready_replicas': ready,
                            'duration': int(elapsed),
                            'logs': logs
                        }
                else:
                    consecutive_failures = 0
                
                # 回调进度（实时推送给前端）
                if progress_callback:
                    await progress_callback(progress)
                
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
    
    async def _get_pods_status(self, namespace: str, deployment_name: str, expected_image: str = None) -> list:
        """获取 Deployment 关联的 Pod 状态列表
        
        Args:
            namespace: 命名空间
            deployment_name: Deployment 名称
            expected_image: 期望的镜像版本（用于过滤，只返回匹配该镜像的 Pod）
        """
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
                # 跳过正在终止的 Pod（deletion_timestamp 不为空表示正在终止）
                if pod.metadata.deletion_timestamp:
                    continue
                
                # 获取容器状态
                container_statuses = pod.status.container_statuses or []
                
                # 检查 Pod 的容器镜像是否匹配期望镜像（如果提供了）
                # 这用于在滚动更新时过滤掉老版本的 Pod
                if expected_image and pod.spec.containers:
                    pod_image = pod.spec.containers[0].image
                    # 简化比较：只比较镜像名和标签
                    if pod_image != expected_image:
                        # 镜像不匹配，这是老版本的 Pod，跳过
                        continue
                
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
                
                # 获取 Pod IP 地址
                pod_ip = pod.status.pod_ip if pod.status else None
                
                pod_status_list.append({
                    'name': pod.metadata.name,
                    'status': status,
                    'phase': pod.status.phase,
                    'ready': all(cs.ready for cs in container_statuses) if container_statuses else False,
                    'restarts': sum(cs.restart_count for cs in container_statuses),
                    'age': pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None,
                    'pod_ip': pod_ip
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
    
    async def _get_failure_reason(self, namespace: str, deployment_name: str) -> str:
        """通过读取 Pod Events 提取失败原因（等价于 kubectl describe pod）"""
        try:
            client_mgr = await self._get_client()
            apps_v1 = client_mgr.apps_v1
            core_v1 = client_mgr.core_v1

            # 获取 Deployment 对应的 Pod
            deployment = await asyncio.to_thread(
                apps_v1.read_namespaced_deployment,
                name=deployment_name,
                namespace=namespace
            )
            selector = deployment.spec.selector.match_labels
            label_selector = ','.join([f"{k}={v}" for k, v in selector.items()])
            pods = await asyncio.to_thread(
                core_v1.list_namespaced_pod,
                namespace=namespace,
                label_selector=label_selector
            )

            reasons = []

            for pod in pods.items:
                pod_name = pod.metadata.name

                # 1. 先检查容器状态中的异常信息（waiting.message 通常包含具体错误）
                container_statuses = pod.status.container_statuses or []
                for cs in container_statuses:
                    if cs.state:
                        if cs.state.waiting and cs.state.waiting.reason:
                            msg = cs.state.waiting.message or ''
                            reasons.append(
                                f"[{pod_name}] 容器 {cs.name} 异常: "
                                f"{cs.state.waiting.reason} - {msg[:200]}"
                            )
                        elif cs.state.terminated and cs.state.terminated.exit_code != 0:
                            msg = cs.state.terminated.message or f"exit code {cs.state.terminated.exit_code}"
                            reasons.append(
                                f"[{pod_name}] 容器 {cs.name} 退出: "
                                f"{cs.state.terminated.reason or 'Error'} - {msg[:200]}"
                            )

                # 2. 读取 Pod Events（kubectl describe pod 的 Events 部分）
                try:
                    events = await asyncio.to_thread(
                        core_v1.list_namespaced_event,
                        namespace=namespace,
                        field_selector=f"involvedObject.name={pod_name}"
                    )
                    for e in events.items:
                        if e.type == 'Warning':
                            reasons.append(
                                f"[{pod_name}] {e.reason}: {(e.message or '')[:300]}"
                            )
                except Exception:
                    pass

            # 去重并返回
            seen = set()
            unique_reasons = []
            for r in reasons:
                if r not in seen:
                    seen.add(r)
                    unique_reasons.append(r)

            return '\n'.join(unique_reasons) if unique_reasons else ''

        except Exception as e:
            logger.error(f"Failed to get failure reason: {e}")
            return ''

    async def _get_failed_pods_logs(self, namespace: str, deployment_name: str, failed_pods: list = None) -> str:
        """获取失败 Pod 的日志"""
        # 复用 _get_pods_logs 方法
        return await self._get_pods_logs(namespace, deployment_name, tail_lines=100)
