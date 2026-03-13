"""
Harbor 镜像仓库服务
提供获取镜像标签列表等功能
"""
import logging
import requests
import re
import subprocess
import json
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote

from app.config import settings

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class HarborService:
    """Harbor 镜像仓库服务"""
    
    def __init__(self, harbor_url: Optional[str] = None, credentials: Optional[Dict[str, str]] = None):
        """
        初始化 Harbor 服务
        
        Args:
            harbor_url: Harbor 地址，如果不提供则使用配置文件中的地址
            credentials: Harbor 认证信息 {'username': 'xxx', 'password': 'xxx'}
        """
        self.base_url = (harbor_url or settings.HARBOR_URL).rstrip('/')
        
        # 优先使用传入的认证信息，其次使用配置文件
        if credentials and 'username' in credentials and 'password' in credentials:
            self.username = credentials['username']
            self.password = credentials['password']
        else:
            self.username = settings.HARBOR_USERNAME
            self.password = settings.HARBOR_PASSWORD
        
        # 保存认证信息供 curl 使用
        self.auth = (self.username, self.password) if self.username and self.password else None
    
    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        """
        发送 GET 请求到 Harbor API
        使用 curl 命令绕过 Python SSL 问题
        """
        url = f"{self.base_url}/api/v2.0{path}"
        logger.info(f"Harbor API request: {url}")
        
        try:
            # 构建 curl 命令
            cmd = ['curl', '-k', '-s', '-u', f'{self.auth[0]}:{self.auth[1]}', url]
            
            # 添加查询参数
            if params:
                for key, value in params.items():
                    cmd.append('-G')
                    cmd.append('--data-urlencode')
                    cmd.append(f'{key}={value}')
            
            # 执行 curl 命令
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"curl failed: {result.stderr}")
                raise Exception(f"curl failed: {result.stderr}")
            
            logger.info(f"Harbor API response: success")
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Harbor API request failed: {e}")
            raise
    
    def parse_image_url(self, image_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        解析镜像地址，提取 harbor 地址、项目和仓库名
        
        Args:
            image_url: 镜像地址，如 harbor.example.com/project/repo:tag
            
        Returns:
            (harbor_host, project, repository) 元组
        """
        try:
            # 移除协议头（如果有）
            image = image_url.replace('https://', '').replace('http://', '')
            
            # 移除 tag
            if ':' in image:
                image = image.rsplit(':', 1)[0]  # 使用 rsplit 避免端口被误删
            
            # 分割路径
            parts = image.split('/')
            
            if len(parts) >= 3:
                # 格式: harbor.example.com/project/repo
                harbor_host = parts[0]
                project = parts[1]
                repository = '/'.join(parts[2:])  # 支持多级路径
                return harbor_host, project, repository
            elif len(parts) == 2:
                # 格式: project/repo (没有 host，使用默认)
                return None, parts[0], parts[1]
            else:
                return None, None, None
        except Exception as e:
            logger.error(f"Failed to parse image URL {image_url}: {e}")
            return None, None, None
    
    def get_image_tags_by_url(self, image_url: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        根据镜像地址获取标签列表（自动提取 harbor 地址、项目、仓库）
        
        Args:
            image_url: 镜像地址
            limit: 返回数量限制
            
        Returns:
            标签列表
        """
        harbor_host, project, repository = self.parse_image_url(image_url)
        
        if not harbor_host or not project or not repository:
            logger.error(f"Cannot parse harbor info from image URL: {image_url}")
            return []
        
        # 根据镜像地址中的 host 构建 harbor URL
        harbor_url = f"https://{harbor_host}"
        
        # 创建临时 Harbor 服务实例，使用镜像中的 host
        # 注意：这里仍然使用配置文件中的认证信息
        # 实际使用时可以通过 kubeconfig 获取对应集群的 Harbor 认证信息
        temp_service = HarborService(harbor_url)
        return temp_service.get_image_tags(project, repository, page_size=limit)
    
    def get_image_tags(
        self,
        project: str,
        repository: str,
        page: int = 1,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取镜像的所有标签
        
        Args:
            project: Harbor 项目名称
            repository: 仓库名称
            page: 页码
            page_size: 每页数量
            
        Returns:
            标签列表，包含标签名和创建时间
        """
        try:
            # URL 编码项目名称和仓库名
            # Harbor API 需要双层 URL 编码
            encoded_project = quote(project, safe='')
            encoded_repo = quote(quote(repository, safe=''), safe='')
            
            # 调用 Harbor API 获取 artifacts
            path = f"/projects/{encoded_project}/repositories/{encoded_repo}/artifacts"
            params = {
                'page': page,
                'page_size': page_size,
                'with_tag': 'true',
                'sort': '-push_time'  # 按推送时间倒序
            }
            
            artifacts = self._get(path, params)
            
            tags = []
            for artifact in artifacts:
                # 提取标签信息
                artifact_tags = artifact.get('tags', [])
                push_time = artifact.get('push_time', '')
                digest = artifact.get('digest', '')
                
                for tag in artifact_tags:
                    tags.append({
                        'tag': tag.get('name'),
                        'digest': digest,
                        'push_time': push_time,
                        'size': artifact.get('size', 0),
                    })
            
            # 按推送时间倒序排序
            tags.sort(key=lambda x: x['push_time'] or '', reverse=True)
            
            logger.info(f"Retrieved {len(tags)} tags for {project}/{repository}")
            return tags
            
        except Exception as e:
            logger.error(f"Failed to get image tags for {project}/{repository}: {e}")
            raise
    
    def get_image_tags_simple(
        self,
        project: str,
        repository: str,
        limit: int = 50
    ) -> List[str]:
        """
        获取镜像标签列表（简化版，只返回标签名）
        
        Args:
            project: Harbor 项目名称
            repository: 仓库名称
            limit: 返回数量限制
            
        Returns:
            标签名列表
        """
        tags = self.get_image_tags(project, repository, page_size=limit)
        return [tag['tag'] for tag in tags if tag['tag']]
    
    def get_image_tags_by_url(self, image_url: str, limit: int = 50) -> List[str]:
        """
        根据镜像地址获取标签列表
        
        Args:
            image_url: 镜像地址
            limit: 返回数量限制
            
        Returns:
            标签名列表
        """
        project, repository = self.parse_image_url(image_url)
        
        if not project or not repository:
            logger.error(f"Cannot parse project/repo from image URL: {image_url}")
            return []
        
        return self.get_image_tags_simple(project, repository, limit)
    
    def test_connection(self) -> bool:
        """
        测试 Harbor 连接
        
        Returns:
            连接是否成功
        """
        try:
            # 尝试获取项目列表来测试连接
            result = self._get("/projects")
            return True
        except Exception as e:
            logger.error(f"Harbor connection test failed: {e}")
            return False
    
    def get_projects(self, page: int = 1, page_size: int = 100) -> List[Dict[str, Any]]:
        """
        获取 Harbor 项目列表
        
        Args:
            page: 页码
            page_size: 每页数量
            
        Returns:
            项目列表
        """
        try:
            path = "/projects"
            params = {
                'page': page,
                'page_size': page_size
            }
            return self._get(path, params)
        except Exception as e:
            logger.error(f"Failed to get projects: {e}")
            raise
    
    def get_repositories(
        self,
        project: str,
        page: int = 1,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取指定项目下的仓库列表
        
        Args:
            project: 项目名称
            page: 页码
            page_size: 每页数量
            
        Returns:
            仓库列表
        """
        try:
            encoded_project = quote(project, safe='')
            path = f"/projects/{encoded_project}/repositories"
            params = {
                'page': page,
                'page_size': page_size
            }
            return self._get(path, params)
        except Exception as e:
            logger.error(f"Failed to get repositories for project {project}: {e}")
            raise


# 创建全局 Harbor 服务实例
harbor_service = HarborService()
