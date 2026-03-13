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


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.status != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role.value}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
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
