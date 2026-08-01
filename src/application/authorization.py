"""Workspace membership authorization."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.identity import Permission, Role, role_allows
from ..infrastructure.models import WorkspaceMembershipModel


class AuthorizationDenied(PermissionError):
    pass


def require_permission(
    session: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    permission: Permission,
    mfa_verified: bool,
) -> Role:
    membership = session.scalar(
        select(WorkspaceMembershipModel).where(
            WorkspaceMembershipModel.user_id == user_id,
            WorkspaceMembershipModel.workspace_id == workspace_id,
        )
    )
    if membership is None or not role_allows(membership.role, permission):
        raise AuthorizationDenied("Permesso non concesso.")
    role = Role(membership.role)
    if role is Role.ADMIN and permission.value.startswith("manage_") and not mfa_verified:
        raise AuthorizationDenied("MFA richiesta per l'azione amministrativa.")
    return role
