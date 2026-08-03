"""Controlled platform bootstrap and workspace membership management."""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.identity import Role
from ..domain.usage import normalized_cost
from ..infrastructure.crypto import PasswordService
from ..infrastructure.models import (
    UsageBudgetModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
)
from .audit_log import append_audit_event


class BootstrapError(RuntimeError):
    pass


def bootstrap_platform(
    session: Session,
    *,
    email: str,
    password: str,
    display_name: str,
    workspace_slug: str,
    workspace_name: str,
    hard_limit: Decimal | str,
    passwords: PasswordService,
) -> tuple[UserModel, WorkspaceModel]:
    if session.scalar(select(func.count()).select_from(UserModel)):
        raise BootstrapError("Bootstrap gia completato.")
    workspace = _new_workspace(workspace_slug, workspace_name)
    user = UserModel(
        email=email.strip().casefold(),
        password_hash=passwords.hash(password),
        display_name=display_name.strip(),
        is_platform_admin=True,
    )
    session.add_all([user, workspace])
    session.flush()
    session.add_all(
        [
            WorkspaceMembershipModel(
                workspace_id=workspace.id, user_id=user.id, role=Role.ADMIN.value
            ),
            UsageBudgetModel(
                workspace_id=workspace.id, hard_limit=normalized_cost(hard_limit)
            ),
        ]
    )
    append_audit_event(
        session,
        action="platform.bootstrap",
        workspace_id=workspace.id,
        actor_user_id=user.id,
        target_type="workspace",
        target_id=str(workspace.id),
    )
    return user, workspace


def create_workspace(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    mfa_verified: bool,
    slug: str,
    name: str,
    hard_limit: Decimal | str,
) -> WorkspaceModel:
    actor = session.get(UserModel, actor_user_id)
    if actor is None or not actor.is_platform_admin or not mfa_verified:
        raise PermissionError("Amministratore di piattaforma con MFA richiesto.")
    workspace = _new_workspace(slug, name)
    session.add(workspace)
    session.flush()
    session.add_all(
        [
            WorkspaceMembershipModel(
                workspace_id=workspace.id,
                user_id=actor.id,
                role=Role.ADMIN.value,
            ),
            UsageBudgetModel(
                workspace_id=workspace.id,
                hard_limit=normalized_cost(hard_limit),
            ),
        ]
    )
    append_audit_event(
        session,
        action="workspace.created",
        workspace_id=workspace.id,
        actor_user_id=actor.id,
        target_type="workspace",
        target_id=str(workspace.id),
    )
    return workspace


def _new_workspace(slug: str, name: str) -> WorkspaceModel:
    normalized_slug = slug.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,78}[a-z0-9]", normalized_slug):
        raise ValueError("Slug workspace non valido.")
    if not name.strip():
        raise ValueError("Nome workspace obbligatorio.")
    return WorkspaceModel(slug=normalized_slug, name=name.strip())
