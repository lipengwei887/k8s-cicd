"""
LDAP 认证服务模块
支持 Windows Active Directory / 标准 LDAP 服务器
"""
import ldap3
from ldap3.core.exceptions import LDAPException
from typing import Optional, Dict, List

from app.config import settings


class LDAPServiceError(Exception):
    """LDAP 服务异常"""
    pass


class LDAPAuthenticationError(LDAPServiceError):
    """LDAP 认证失败"""
    pass


class LDAPService:
    """
    LDAP 认证服务
    支持异步方式的 LDAP 用户认证
    """
    
    def __init__(self):
        self._server: Optional[ldap3.Server] = None
        self._initialize_server()
    
    def _initialize_server(self):
        """初始化 LDAP 服务器连接"""
        if not settings.LDAP_ENABLED:
            return
        
        try:
            self._server = ldap3.Server(
                host=settings.LDAP_SERVER,
                port=settings.LDAP_PORT,
                use_ssl=settings.LDAP_USE_SSL,
                connect_timeout=10
            )
        except Exception as e:
            raise LDAPServiceError(f"Failed to initialize LDAP server: {e}")
    
    def _get_connection(self, user_dn: str = None, password: str = None) -> ldap3.Connection:
        """
        获取 LDAP 连接
        
        Args:
            user_dn: 用户 DN，为空则使用服务账号
            password: 密码，为空则使用服务账号密码
        
        Returns:
            ldap3.Connection: LDAP 连接对象
        """
        bind_dn = user_dn or settings.LDAP_BIND_DN
        bind_password = password or settings.LDAP_BIND_PASSWORD
        
        if not bind_dn:
            raise LDAPServiceError("LDAP bind DN not configured")
        
        conn = ldap3.Connection(
            self._server,
            user=bind_dn,
            password=bind_password,
            auto_bind=False,
            read_only=True
        )
        return conn
    
    async def test_connection(self) -> bool:
        """
        测试 LDAP 连接是否可用
        
        Returns:
            bool: 连接成功返回 True
        """
        if not settings.LDAP_ENABLED or not self._server:
            return False
        
        try:
            conn = self._get_connection()
            if conn.bind():
                conn.unbind()
                return True
            return False
        except LDAPException:
            return False
        except Exception:
            return False
    
    async def search_user(self, username: str) -> Optional[Dict]:
        """
        搜索 LDAP 用户
        
        Args:
            username: 用户名（sAMAccountName）
        
        Returns:
            Optional[Dict]: 用户信息字典，未找到返回 None
        """
        if not settings.LDAP_ENABLED or not self._server:
            return None
        
        try:
            # 使用服务账号绑定
            conn = self._get_connection()
            if not conn.bind():
                raise LDAPServiceError("Failed to bind with service account")
            
            # 构建搜索过滤器
            search_filter = settings.LDAP_USER_FILTER.format(username=username)
            
            # 执行搜索
            conn.search(
                search_base=settings.LDAP_USER_BASE_DN,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=settings.ldap_user_attrs_list
            )
            
            if not conn.entries:
                return None
            
            # 提取用户信息
            entry = conn.entries[0]
            user_info = {
                "dn": entry.entry_dn,
                "username": username,
            }
            
            # 提取属性
            if hasattr(entry, 'sAMAccountName') and entry.sAMAccountName:
                user_info["username"] = entry.sAMAccountName.value
            
            if hasattr(entry, 'mail') and entry.mail:
                user_info["email"] = entry.mail.value
            else:
                user_info["email"] = f"{username}@tongfu.com"
            
            if hasattr(entry, 'displayName') and entry.displayName:
                user_info["real_name"] = entry.displayName.value
            else:
                user_info["real_name"] = username
            
            # 可选属性
            if hasattr(entry, 'department') and entry.department:
                user_info["department"] = entry.department.value
            
            if hasattr(entry, 'telephoneNumber') and entry.telephoneNumber:
                user_info["phone"] = entry.telephoneNumber.value
            
            conn.unbind()
            return user_info
            
        except LDAPException as e:
            raise LDAPServiceError(f"LDAP search failed: {e}")
        except Exception as e:
            raise LDAPServiceError(f"Unexpected error during search: {e}")
    
    async def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """
        验证 LDAP 用户凭据
        
        Args:
            username: 用户名
            password: 密码
        
        Returns:
            Optional[Dict]: 认证成功返回用户信息，失败返回 None
        
        Raises:
            LDAPAuthenticationError: 认证失败
            LDAPServiceError: 服务异常
        """
        if not settings.LDAP_ENABLED:
            return None
        
        if not username or not password:
            return None
        
        try:
            # 1. 先搜索用户获取 DN
            user_info = await self.search_user(username)
            if not user_info:
                return None
            
            user_dn = user_info.get("dn")
            if not user_dn:
                raise LDAPServiceError("User DN not found in search result")
            
            # 2. 使用用户凭据进行绑定验证
            user_conn = ldap3.Connection(
                self._server,
                user=user_dn,
                password=password,
                auto_bind=False
            )
            
            if not user_conn.bind():
                # 认证失败
                user_conn.unbind()
                return None
            
            # 认证成功
            user_conn.unbind()
            
            # 返回用户信息（不包含 dn）
            return {
                "username": user_info["username"],
                "email": user_info["email"],
                "real_name": user_info["real_name"],
                "department": user_info.get("department"),
                "phone": user_info.get("phone")
            }
            
        except LDAPException as e:
            raise LDAPAuthenticationError(f"LDAP authentication error: {e}")
        except Exception as e:
            raise LDAPServiceError(f"Unexpected error during authentication: {e}")
    
    async def get_user_groups(self, username: str) -> List[str]:
        """
        获取用户的 LDAP 组信息（用于后续权限映射）
        
        Args:
            username: 用户名
        
        Returns:
            List[str]: 用户所属组列表
        """
        # TODO: 后续实现 AD 组同步功能
        return []


# 全局 LDAP 服务实例
ldap_service = LDAPService()
