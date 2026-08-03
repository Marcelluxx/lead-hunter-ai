"""Identity, role and permission contracts."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(str, Enum):
    MANAGE_USERS = "manage_users"
    MANAGE_WORKSPACE = "manage_workspace"
    MANAGE_SECRETS = "manage_secrets"
    MANAGE_BUDGET = "manage_budget"
    START_JOB = "start_job"
    CANCEL_JOB = "cancel_job"
    VIEW_RESULTS = "view_results"
    EXPORT_RESULTS = "export_results"
    VIEW_AUDIT_LOG = "view_audit_log"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.OPERATOR: frozenset(
        {
            Permission.START_JOB,
            Permission.CANCEL_JOB,
            Permission.VIEW_RESULTS,
            Permission.EXPORT_RESULTS,
        }
    ),
    Role.VIEWER: frozenset({Permission.VIEW_RESULTS, Permission.VIEW_AUDIT_LOG}),
}


def role_allows(role: Role | str, permission: Permission) -> bool:
    try:
        normalized = role if isinstance(role, Role) else Role(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS[normalized]
