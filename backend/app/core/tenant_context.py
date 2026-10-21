from contextvars import ContextVar
from typing import Optional
import uuid

# Context variables for the active tenant, branch, and user per async request
current_tenant_id: ContextVar[Optional[uuid.UUID]] = ContextVar("current_tenant_id", default=None)
current_branch_id: ContextVar[Optional[uuid.UUID]] = ContextVar("current_branch_id", default=None)
current_user_id: ContextVar[Optional[uuid.UUID]] = ContextVar("current_user_id", default=None)


def set_tenant_context(tenant_id: Optional[uuid.UUID], branch_id: Optional[uuid.UUID] = None, user_id: Optional[uuid.UUID] = None):
    current_tenant_id.set(tenant_id)
    if branch_id:
        current_branch_id.set(branch_id)
    if user_id:
        current_user_id.set(user_id)


def get_current_tenant_id() -> Optional[uuid.UUID]:
    return current_tenant_id.get()


def get_current_branch_id() -> Optional[uuid.UUID]:
    return current_branch_id.get()


def get_current_user_id() -> Optional[uuid.UUID]:
    return current_user_id.get()


def clear_tenant_context():
    current_tenant_id.set(None)
    current_branch_id.set(None)
    current_user_id.set(None)
