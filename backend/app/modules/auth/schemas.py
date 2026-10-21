import uuid
from typing import List, Optional
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SwitchTenantRequest(BaseModel):
    tenant_id: uuid.UUID
    branch_id: Optional[uuid.UUID] = None


class TenantBriefResponse(BaseModel):
    id: uuid.UUID
    rfc: str
    legal_name: str
    trade_name: Optional[str] = None
    default_branch_id: Optional[uuid.UUID] = None
    roles: List[str] = []

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_superadmin: bool
    is_active: bool
    tenants: List[TenantBriefResponse] = []

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse
    active_tenant_id: Optional[uuid.UUID] = None
    active_branch_id: Optional[uuid.UUID] = None
    permissions: List[str] = []

