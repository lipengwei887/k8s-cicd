from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
import hashlib

from app.config import settings


class SecretManager:
    """敏感信息加密管理器"""
    
    def __init__(self, master_key: Optional[str] = None):
        """
        初始化加密管理器
        
        Args:
            master_key: 主密钥 (应从环境变量或 Vault 获取)
        """
        self.master_key = master_key or settings.ENCRYPTION_KEY or settings.SECRET_KEY
        self._fernet = self._create_fernet(self.master_key)
    
    def _create_fernet(self, key: str) -> Fernet:
        """创建 Fernet 实例"""
        # 使用 PBKDF2 从密码派生密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'k8s-platform-salt',  # 生产环境应使用随机 salt
            iterations=100000,
        )
        key_bytes = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        return Fernet(key_bytes)
    
    def encrypt(self, plaintext: str) -> str:
        """加密明文"""
        if not plaintext:
            return ''
        return self._fernet.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """解密密文"""
        if not ciphertext:
            return ''
        return self._fernet.decrypt(ciphertext.encode()).decode()
    
    @staticmethod
    def generate_key() -> str:
        """生成新的加密密钥"""
        return Fernet.generate_key().decode()


# 全局加密管理器实例
secret_manager = SecretManager()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码 (使用 SHA256)"""
    return get_password_hash(plain_password) == hashed_password


def get_password_hash(password: str) -> str:
    """获取密码哈希 (使用 SHA256)"""
    return hashlib.sha256(password.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """解码 JWT 令牌"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
