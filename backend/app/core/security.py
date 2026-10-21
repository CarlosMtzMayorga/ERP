from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
from jose import jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import hashlib

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, Any],
    tenant_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    is_superadmin: bool = False,
    expires_delta: Optional[timedelta] = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "branch_id": str(branch_id) if branch_id else None,
        "is_superadmin": is_superadmin
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def get_fernet_cipher() -> Fernet:
    """Derives a Fernet 32-byte url-safe base64 key from CSD_ENCRYPTION_KEY."""
    raw_key = hashlib.sha256(settings.CSD_ENCRYPTION_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(raw_key)
    return Fernet(fernet_key)


def encrypt_csd_key(private_key_pem: bytes) -> str:
    cipher = get_fernet_cipher()
    return cipher.encrypt(private_key_pem).decode("utf-8")


def decrypt_csd_key(encrypted_key_str: str) -> bytes:
    cipher = get_fernet_cipher()
    return cipher.decrypt(encrypted_key_str.encode("utf-8"))
