"""
K8s 集群同步服务
自动从集群同步命名空间和 Deployment 信息
"""
import logging
from typing import List, Dict, Any, Optional
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
import yaml
import tempfile
import os

logger = logging.getLogger(__name__)


class K8sSyncService:
    """K8s 集群同步服务"""
    
    def __init__(self, kubeconfig_content: str):
        """
        初始化 K8s 同步服务
        
        Args:
            kubeconfig_content: kubeconfig 文件内容
        """
        self.kubeconfig_content = kubeconfig_content
        self._apps_v1: Optional[client.AppsV1Api] = None
        self._core_v1: Optional[client.CoreV1Api] = None
        self._init_client()
    
    def _init_client(self):
        """初始化 K8s 客户端"""
        try:
            # 将 kubeconfig 写入临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(self.kubeconfig_content)
                temp_path = f.name
            
            # 加载 kubeconfig
            config.load_kube_config(config_file=temp_path)
            
            # 创建客户端
            self._apps_v1 = client.AppsV1Api()
            self._core_v1 = client.CoreV1Api()
            
            # 删除临时文件
            os.unlink(temp_path)
            
            logger.info("K8s client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize K8s client: {e}")
            raise
    
    def get_harbor_secret(self, namespace: str = "default", secret_name: str = "harbor-secret") -> Optional[Dict[str, str]]:
        """
        从 K8s Secret 获取 Harbor 认证信息
        支持两种格式：
        1. 直接包含 username/password 字段的 secret
        2. .dockerconfigjson 格式的 secret（kubernetes.io/dockerconfigjson 类型）
        
        Args:
            namespace: Secret 所在的命名空间
            secret_name: Secret 名称
            
        Returns:
            包含 username 和 password 的字典，如果未找到则返回 None
        """
        try:
            secret = self._core_v1.read_namespaced_secret(secret_name, namespace)
            
            # 从 Secret 中提取数据
            data = secret.data or {}
            
            # 尝试不同的 key 名称
            username = None
            password = None
            
            # 常见的 username key 名称
            for key in ['username', 'user', 'accessKey', 'access-key', 'ACCESS_KEY']:
                if key in data:
                    import base64
                    username = base64.b64decode(data[key]).decode('utf-8')
                    break
            
            # 常见的 password key 名称
            for key in ['password', 'pass', 'secretKey', 'secret-key', 'SECRET_KEY', 'token']:
                if key in data:
                    import base64
                    password = base64.b64decode(data[key]).decode('utf-8')
                    break
            
            # 如果直接字段没找到，尝试解析 .dockerconfigjson 格式
            if not (username and password) and '.dockerconfigjson' in data:
                try:
                    import json
                    import base64
                    docker_config = base64.b64decode(data['.dockerconfigjson']).decode('utf-8')
                    config = json.loads(docker_config)
                    
                    # 从 auths 中提取认证信息
                    auths = config.get('auths', {})
                    for registry, auth_data in auths.items():
                        # 优先找包含 harbor 的 registry
                        if 'harbor' in registry.lower():
                            auth = auth_data.get('auth', '')
                            if auth:
                                # auth 是 base64(username:password) 格式
                                decoded_auth = base64.b64decode(auth).decode('utf-8')
                                if ':' in decoded_auth:
                                    username, password = decoded_auth.split(':', 1)
                                    logger.info(f"Found Harbor credentials in .dockerconfigjson for registry: {registry}")
                                    break
                            # 也可以直接有 username/password 字段
                            if not username and 'username' in auth_data:
                                username = auth_data['username']
                            if not password and 'password' in auth_data:
                                password = auth_data['password']
                    
                    # 如果没找到 harbor 特定的，取第一个
                    if not (username and password) and auths:
                        first_registry = list(auths.values())[0]
                        auth = first_registry.get('auth', '')
                        if auth:
                            decoded_auth = base64.b64decode(auth).decode('utf-8')
                            if ':' in decoded_auth:
                                username, password = decoded_auth.split(':', 1)
                                logger.info(f"Found credentials in .dockerconfigjson (first registry)")
                except Exception as e:
                    logger.warning(f"Failed to parse .dockerconfigjson: {e}")
            
            if username and password:
                logger.info(f"Found Harbor credentials in secret {secret_name}")
                return {'username': username, 'password': password}
            else:
                logger.warning(f"Could not find username/password in secret {secret_name}")
                return None
                
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Secret {secret_name} not found in namespace {namespace}")
            else:
                logger.error(f"Failed to get secret {secret_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading secret {secret_name}: {e}")
            return None
    
    def find_harbor_secret(self, namespace: str = "default") -> Optional[Dict[str, str]]:
        """
        在指定命名空间中查找 Harbor 相关的 Secret
        
        Args:
            namespace: 命名空间
            
        Returns:
            包含 username 和 password 的字典，如果未找到则返回 None
        """
        try:
            # 常见的 Harbor Secret 名称模式
            secret_patterns = ['harbor', 'registry', 'docker', 'image-pull']
            
            secrets = self._core_v1.list_namespaced_secret(namespace)
            
            for secret in secrets.items:
                secret_name = secret.metadata.name.lower()
                
                # 检查是否匹配 Harbor 相关模式
                for pattern in secret_patterns:
                    if pattern in secret_name:
                        logger.info(f"Found potential Harbor secret: {secret.metadata.name}")
                        creds = self.get_harbor_secret(namespace, secret.metadata.name)
                        if creds:
                            return creds
            
            logger.warning(f"No Harbor secret found in namespace {namespace}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to list secrets in namespace {namespace}: {e}")
            return None
    
    # K8s 系统命名空间列表，这些命名空间将被忽略
    # 包括：kube- 开头、ack- 开头、以及其他已知的系统命名空间
    # 注意：default 命名空间不过滤，用户可能在此部署应用
    SYSTEM_NAMESPACES = {
        'kube-system', 'kube-public', 'kube-node-lease',
        'kubernetes-dashboard', 'ingress-nginx',
        'calico-system', 'tigera-operator', 'cattle-system',
        'cattle-prometheus', 'cattle-logging', 'longhorn-system',
        'istio-system', 'knative-serving', 'cert-manager',
        'gatekeeper-system', 'kubevirt', 'openshift',
    }
    
    # 系统命名空间前缀，以这些前缀开头的命名空间将被忽略
    SYSTEM_NAMESPACE_PREFIXES = ('kube-', 'ack-')
    
    def sync_namespaces(self) -> List[Dict[str, Any]]:
        """
        同步命名空间列表（排除系统命名空间）
        
        Returns:
            命名空间列表
        """
        try:
            namespaces = self._core_v1.list_namespace()
            result = []
            
            for ns in namespaces.items:
                ns_name = ns.metadata.name
                
                # 跳过系统命名空间（精确匹配或前缀匹配）
                if ns_name in self.SYSTEM_NAMESPACES:
                    logger.debug(f"Skipping system namespace: {ns_name}")
                    continue
                
                # 跳过以系统前缀开头的命名空间
                if ns_name.startswith(self.SYSTEM_NAMESPACE_PREFIXES):
                    logger.debug(f"Skipping system namespace (prefix match): {ns_name}")
                    continue
                
                # 根据命名空间名称判断环境类型
                env_type = self._detect_env_type(ns_name)
                
                result.append({
                    'name': ns_name,
                    'display_name': ns_name,
                    'env_type': env_type,
                    'status': 1,
                    'description': f'从集群同步的命名空间: {ns_name}'
                })
            
            logger.info(f"Synced {len(result)} namespaces (excluded {len(namespaces.items) - len(result)} system namespaces)")
            return result
            
        except ApiException as e:
            logger.error(f"Failed to sync namespaces: {e}")
            raise
    
    def sync_deployments(self, namespace: str) -> List[Dict[str, Any]]:
        """
        同步指定命名空间下的 Deployment
        
        Args:
            namespace: 命名空间名称
            
        Returns:
            Deployment 列表
        """
        try:
            deployments = self._apps_v1.list_namespaced_deployment(namespace)
            result = []
            
            for deploy in deployments.items:
                # 获取容器信息
                containers = deploy.spec.template.spec.containers
                main_container = containers[0] if containers else None
                
                # 获取当前镜像地址
                current_image = main_container.image if main_container else None
                
                service_info = {
                    'name': deploy.metadata.name,
                    'display_name': deploy.metadata.name,
                    'type': 'deployment',
                    'deploy_name': deploy.metadata.name,
                    'container_name': main_container.name if main_container else deploy.metadata.name,
                    'current_image': current_image,  # 保存当前镜像地址
                    'replicas': deploy.spec.replicas or 1,
                    'status': 1,
                    'description': f'从集群同步的 Deployment: {deploy.metadata.name}'
                }
                
                # 尝试从镜像中提取 harbor 项目信息
                if current_image:
                    image_info = self._parse_image(current_image)
                    service_info.update(image_info)
                
                # 获取端口信息
                if main_container and main_container.ports:
                    service_info['port'] = main_container.ports[0].container_port
                
                result.append(service_info)
            
            logger.info(f"Synced {len(result)} deployments in namespace {namespace}")
            return result
            
        except ApiException as e:
            logger.error(f"Failed to sync deployments: {e}")
            raise
    
    def sync_statefulsets(self, namespace: str) -> List[Dict[str, Any]]:
        """
        同步指定命名空间下的 StatefulSet
        
        Args:
            namespace: 命名空间名称
            
        Returns:
            StatefulSet 列表
        """
        try:
            statefulsets = self._apps_v1.list_namespaced_stateful_set(namespace)
            result = []
            
            for sts in statefulsets.items:
                containers = sts.spec.template.spec.containers
                main_container = containers[0] if containers else None
                
                # 获取当前镜像地址
                current_image = main_container.image if main_container else None
                
                service_info = {
                    'name': sts.metadata.name,
                    'display_name': sts.metadata.name,
                    'type': 'statefulset',
                    'deploy_name': sts.metadata.name,
                    'container_name': main_container.name if main_container else sts.metadata.name,
                    'current_image': current_image,  # 保存当前镜像地址
                    'replicas': sts.spec.replicas or 1,
                    'status': 1,
                    'description': f'从集群同步的 StatefulSet: {sts.metadata.name}'
                }
                
                if current_image:
                    image_info = self._parse_image(current_image)
                    service_info.update(image_info)
                
                if main_container and main_container.ports:
                    service_info['port'] = main_container.ports[0].container_port
                
                result.append(service_info)
            
            logger.info(f"Synced {len(result)} statefulsets in namespace {namespace}")
            return result
            
        except ApiException as e:
            logger.error(f"Failed to sync statefulsets: {e}")
            raise
    
    def _detect_env_type(self, namespace_name: str) -> str:
        """
        根据命名空间名称检测环境类型
        
        Args:
            namespace_name: 命名空间名称
            
        Returns:
            环境类型: dev, test, staging, prod
        """
        name_lower = namespace_name.lower()
        
        if any(keyword in name_lower for keyword in ['prod', 'production', '线上', '生产']):
            return 'prod'
        elif any(keyword in name_lower for keyword in ['staging', 'pre', '灰度']):
            return 'staging'
        elif any(keyword in name_lower for keyword in ['test', 'testing', '测试']):
            return 'test'
        elif any(keyword in name_lower for keyword in ['dev', 'develop', '开发']):
            return 'dev'
        else:
            # 默认根据常见命名规则判断
            if 'prod' in name_lower:
                return 'prod'
            elif 'test' in name_lower:
                return 'test'
            elif 'dev' in name_lower:
                return 'dev'
            else:
                return 'dev'  # 默认开发环境
    
    def _parse_image(self, image: str) -> Dict[str, str]:
        """
        解析镜像地址，提取 harbor 项目信息
        
        Args:
            image: 镜像地址，如 harbor.example.com/project/repo:tag
            
        Returns:
            包含 harbor_project 和 harbor_repo 的字典
        """
        try:
            # 移除 tag
            if ':' in image:
                image = image.split(':')[0]
            
            # 解析路径
            parts = image.split('/')
            
            if len(parts) >= 3:
                # 格式: harbor.example.com/project/repo
                return {
                    'harbor_project': parts[1],
                    'harbor_repo': '/'.join(parts[2:])
                }
            elif len(parts) == 2:
                # 格式: project/repo
                return {
                    'harbor_project': parts[0],
                    'harbor_repo': parts[1]
                }
            else:
                return {
                    'harbor_project': 'library',
                    'harbor_repo': parts[0]
                }
        except Exception as e:
            logger.warning(f"Failed to parse image {image}: {e}")
            return {
                'harbor_project': 'library',
                'harbor_repo': 'unknown'
            }
    
    def test_connection(self) -> bool:
        """
        测试集群连接
        
        Returns:
            连接是否成功
        """
        try:
            # 尝试获取命名空间列表来测试连接
            self._core_v1.list_namespace(limit=1)
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """
        获取集群基本信息
        
        Returns:
            集群信息
        """
        try:
            # 获取集群版本信息
            version = self._core_v1.api_client.call_api(
                '/version', 'GET', auth_settings=['BearerToken']
            )
            
            # 获取节点信息
            nodes = self._core_v1.list_node()
            
            return {
                'version': version,
                'node_count': len(nodes.items),
                'nodes': [
                    {
                        'name': node.metadata.name,
                        'status': node.status.conditions[-1].type if node.status.conditions else 'Unknown'
                    }
                    for node in nodes.items
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get cluster info: {e}")
            return {}
