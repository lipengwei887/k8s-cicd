"""
LDAP 管理接口
提供 LDAP 连接测试和状态查询等功能
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.authorization import require_permission, user_has_permission_code
from app.models.user import User
from app.api.v1.auth import get_current_active_user
from app.config import settings
from app.services.ldap_service import ldap_service, LDAPServiceError

router = APIRouter()


@router.get("/status")
async def get_ldap_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取 LDAP 配置状态
    
    普通用户可查看是否启用，管理员可查看详细配置（脱敏）
    """
    is_admin = await user_has_permission_code(db, current_user, "user:manage")
    
    response = {
        "enabled": settings.LDAP_ENABLED,
        "server": settings.LDAP_SERVER if is_admin else None,
        "port": settings.LDAP_PORT if is_admin else None,
        "use_ssl": settings.LDAP_USE_SSL if is_admin else None,
    }
    
    # 非管理员移除 None 值
    if not is_admin:
        response = {"enabled": settings.LDAP_ENABLED}
    
    return response


@router.post("/test-connection")
async def test_ldap_connection(
    current_user: User = Depends(require_permission("user:manage"))
):
    """
    测试 LDAP 连接（仅管理员）
    
    返回连接测试结果和详细信息
    """
    if not settings.LDAP_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LDAP is not enabled"
        )
    
    try:
        is_connected = await ldap_service.test_connection()
        
        if is_connected:
            return {
                "success": True,
                "message": "LDAP connection successful",
                "server": settings.LDAP_SERVER,
                "port": settings.LDAP_PORT
            }
        else:
            return {
                "success": False,
                "message": "Failed to connect to LDAP server",
                "server": settings.LDAP_SERVER,
                "port": settings.LDAP_PORT
            }
            
    except LDAPServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LDAP service error: {str(e)}"
        )


@router.post("/test-user")
async def test_ldap_user(
    username: str,
    current_user: User = Depends(require_permission("user:manage"))
):
    """
    测试 LDAP 用户查询（仅管理员）
    
    用于验证用户搜索过滤器配置是否正确
    """
    if not settings.LDAP_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LDAP is not enabled"
        )
    
    try:
        user_info = await ldap_service.search_user(username)
        
        if user_info:
            return {
                "found": True,
                "user": {
                    "username": user_info.get("username"),
                    "email": user_info.get("email"),
                    "real_name": user_info.get("real_name"),
                    "department": user_info.get("department")
                }
            }
        else:
            return {
                "found": False,
                "message": f"User '{username}' not found in LDAP"
            }
            
    except LDAPServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LDAP search error: {str(e)}"
        )


@router.get("/config")
async def get_ldap_config(
    current_user: User = Depends(require_permission("user:manage"))
):
    """
    获取 LDAP 配置（仅管理员，密码脱敏）
    """
    return {
        "enabled": settings.LDAP_ENABLED,
        "server": settings.LDAP_SERVER,
        "port": settings.LDAP_PORT,
        "use_ssl": settings.LDAP_USE_SSL,
        "bind_dn": settings.LDAP_BIND_DN,
        "bind_password_configured": bool(settings.LDAP_BIND_PASSWORD),
        "user_base_dn": settings.LDAP_USER_BASE_DN,
        "user_filter": settings.LDAP_USER_FILTER,
        "user_attrs": settings.ldap_user_attrs_list
    }
