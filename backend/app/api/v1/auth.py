from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
from typing import Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserLogin, Token, UserResponse
from app.core.security import verify_password, create_access_token, decode_access_token, get_password_hash
from app.config import settings

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if user is None or user.status != 1:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    if current_user.status != 1:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def _create_token_response(user: User) -> dict:
    """创建 Token 响应"""
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role.value if user.role else None}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "real_name": user.real_name,
            "role": user.role.value if user.role else None,
            "status": user.status,
            "is_superuser": user.is_superuser,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    }


async def _authenticate_local(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """
    本地认证
    """
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    return user


async def _authenticate_ldap(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """
    LDAP 认证
    认证成功后自动创建或更新本地用户
    """
    if not settings.LDAP_ENABLED:
        return None
    
    from app.services.ldap_service import ldap_service, LDAPServiceError
    
    try:
        # LDAP 认证
        ldap_user = await ldap_service.authenticate(username, password)
        
        if not ldap_user:
            return None
        
        # 查询本地是否已存在该用户
        result = await db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # 更新现有用户信息
            user.email = ldap_user["email"]
            user.real_name = ldap_user["real_name"]
            user.status = 1  # 确保用户启用
            # LDAP 用户不存储密码
        else:
            # 创建新用户
            # LDAP 用户使用随机密码占位（无法用于本地登录）
            from app.core.security import get_password_hash
            random_password = get_password_hash(f"ldap_{username}_{ldap_user['email']}_placeholder")
            user = User(
                username=ldap_user["username"],
                email=ldap_user["email"],
                real_name=ldap_user["real_name"],
                password_hash=random_password,  # LDAP 用户使用占位密码
                status=1,
                role=UserRole.DEVELOPER,  # 默认角色
                is_superuser=False
            )
            db.add(user)
        
        await db.commit()
        await db.refresh(user)
        return user
        
    except LDAPServiceError as e:
        # LDAP 服务异常，记录日志但不暴露细节
        print(f"LDAP service error: {e}")
        return None


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录 - 支持本地和 LDAP 认证
    
    认证流程：
    1. 先尝试本地认证
    2. 本地失败且 LDAP 启用时，尝试 LDAP 认证
    3. LDAP 认证成功自动创建/更新本地用户
    """
    username = form_data.username
    password = form_data.password
    
    # 1. 尝试本地认证
    user = await _authenticate_local(db, username, password)
    
    # 2. 本地认证失败，尝试 LDAP
    if not user and settings.LDAP_ENABLED:
        user = await _authenticate_ldap(db, username, password)
    
    # 3. 全部失败
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查用户状态
    if user.status != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # 更新最后登录时间
    from datetime import datetime
    user.last_login_at = datetime.now()
    await db.commit()
    
    # 预加载所有需要的字段（避免懒加载问题）
    user_id = user.id
    user_username = user.username
    user_email = user.email
    user_real_name = user.real_name
    user_role = user.role.value if user.role else None
    user_status = user.status
    user_is_superuser = user.is_superuser
    user_last_login_at = user.last_login_at.isoformat() if user.last_login_at else None
    user_created_at = user.created_at.isoformat() if user.created_at else None
    
    # 构建响应
    access_token = create_access_token(
        data={"sub": str(user_id), "username": user_username, "role": user_role}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "username": user_username,
            "email": user_email,
            "real_name": user_real_name,
            "role": user_role,
            "status": user_status,
            "is_superuser": user_is_superuser,
            "last_login_at": user_last_login_at,
            "created_at": user_created_at
        }
    }


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户信息，包含权限列表"""
    from app.services.rbac_service import RBACService
    
    # 超级管理员拥有所有权限
    if current_user.is_superuser:
        # 从角色权限关联表中获取所有权限代码
        from app.models.role import RBACPermission
        result = await db.execute(select(RBACPermission))
        all_permissions = result.scalars().all()
        permission_codes = [p.code for p in all_permissions]
    else:
        # 获取用户权限列表
        rbac_service = RBACService(db)
        permission_objects = await rbac_service.get_user_permissions(current_user.id)
        # 提取权限代码为字符串列表
        permission_codes = [p.get("permission_code") for p in permission_objects if p.get("permission_code")]
    
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "real_name": current_user.real_name,
        "role": current_user.role.value if current_user.role else None,
        "status": current_user.status,
        "is_superuser": current_user.is_superuser,
        "last_login_at": current_user.last_login_at,
        "created_at": current_user.created_at,
        "permissions": permission_codes
    }


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_active_user)):
    """用户登出 (前端清除 token 即可)"""
    return {"message": "Successfully logged out"}


async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """要求管理员权限"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required"
        )
    return current_user


async def require_developer_or_above(current_user: User = Depends(get_current_active_user)) -> User:
    """要求开发人员或更高权限"""
    if current_user.role not in [UserRole.ADMIN, UserRole.DEVELOPER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Developer permission required"
        )
    return current_user
