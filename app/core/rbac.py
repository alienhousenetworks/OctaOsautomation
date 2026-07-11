from enum import Enum
from typing import List, Dict
from fastapi import Depends, HTTPException, status
from app.api import deps
from app.models.base import User


class Action(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"


class Resource(str, Enum):
    LEADS = "leads"
    USERS = "users"
    TICKETS = "tickets"
    CAMPAIGNS = "campaigns"
    SETTINGS = "settings"
    INTEGRATIONS = "integrations"
    AUDIT_LOGS = "audit_logs"
    MEETINGS = "meetings"
    CREDENTIALS = "credentials"
    PUBLISH = "publish"
    BILLING = "billing"
    HR = "hr"
    CEO = "ceo"
    FINANCE = "finance"
    VIDEOS = "videos"


# Canonical roles: admin | manager | agent | read_only
# Legacy aliases mapped in has_permission / normalize_role
ROLE_PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    "super_admin": {
        "*": ["*"]
    },
    "admin": {
        "leads": ["create", "read", "update", "delete", "execute"],
        "users": ["create", "read", "update", "delete"],
        "tickets": ["create", "read", "update", "delete", "execute"],
        "campaigns": ["create", "read", "update", "delete", "execute"],
        "settings": ["create", "read", "update", "delete", "execute"],
        "integrations": ["create", "read", "update", "delete", "execute"],
        "meetings": ["create", "read", "update", "delete", "execute"],
        "audit_logs": ["read"],
        "credentials": ["create", "read", "update", "delete"],
        "publish": ["create", "read", "update", "execute"],
        "billing": ["create", "read", "update", "delete", "execute"],
        "hr": ["create", "read", "update", "delete", "execute"],
        "ceo": ["create", "read", "update", "execute"],
        "finance": ["create", "read", "update", "delete", "execute"],
        "videos": ["create", "read", "update", "delete", "execute"],
    },
    "manager": {
        "leads": ["create", "read", "update", "execute"],
        "users": ["read"],
        "tickets": ["create", "read", "update", "execute"],
        "campaigns": ["create", "read", "update", "execute"],
        "settings": ["read", "update", "execute"],
        "integrations": ["read"],
        "meetings": ["create", "read", "update", "execute"],
        "audit_logs": ["read"],
        "credentials": ["read"],
        "publish": ["create", "read", "update", "execute"],
        "billing": ["read"],
        "hr": ["create", "read", "update", "execute"],
        "ceo": ["read", "execute"],
        "finance": ["read", "create", "update"],
        "videos": ["create", "read", "update", "execute"],
    },
    "agent": {
        "leads": ["create", "read", "update"],
        "users": ["read"],
        "tickets": ["create", "read", "update"],
        "campaigns": ["read", "create", "update"],
        "settings": ["read"],
        "integrations": ["read"],
        "meetings": ["create", "read"],
        "publish": ["read"],
        "hr": ["read", "create", "update"],
        "ceo": ["read"],
        "finance": ["read"],
        "videos": ["read", "create"],
    },
    "read_only": {
        "leads": ["read"],
        "users": ["read"],
        "tickets": ["read"],
        "campaigns": ["read"],
        "settings": ["read"],
        "meetings": ["read"],
        "publish": ["read"],
        "billing": ["read"],
        "hr": ["read"],
        "ceo": ["read"],
        "finance": ["read"],
        "videos": ["read"],
        "audit_logs": ["read"],
    },
}


def normalize_role(user_role: str) -> str:
    role = (user_role or "agent").lower()
    aliases = {
        "organization_admin": "admin",
        "admin": "admin",
        "member": "agent",
        "employee": "agent",
        "manager": "manager",
        "read_only": "read_only",
        "readonly": "read_only",
        "viewer": "read_only",
        "superuser": "super_admin",
        "system_admin": "super_admin",
        "super_admin": "super_admin",
    }
    return aliases.get(role, role)


def has_permission(user_role: str, resource: str, action: str) -> bool:
    role = normalize_role(user_role)
    permissions = ROLE_PERMISSIONS.get(role, {})

    if "*" in permissions and ("*" in permissions["*"] or action in permissions["*"]):
        return True

    if resource in permissions:
        allowed_actions = permissions[resource]
        return "*" in allowed_actions or action in allowed_actions

    return False


def require_permission(resource: Resource, action: Action):
    def dependency(current_user: User = Depends(deps.get_current_user)) -> User:
        if getattr(current_user, "is_system_admin", False) or getattr(current_user, "is_superuser", False):
            return current_user

        if not has_permission(current_user.role, resource.value, action.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: you do not have permission to {action.value} {resource.value}.",
            )
        return current_user

    return dependency
