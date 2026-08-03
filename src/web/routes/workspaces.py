from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...application.authentication import AuthContext
from ...application.authorization import AuthorizationDenied, require_permission
from ...domain.identity import Permission
from ..dependencies import WebRuntime, current_auth, db_session, runtime, workspace_uuid
from ..schemas import SecretStatusResponse, SecretWriteRequest


router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["workspaces"])


@router.put("/secrets/{provider}", response_model=SecretStatusResponse)
def put_secret(
    workspace_id: str,
    provider: str,
    body: SecretWriteRequest,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    workspace = workspace_uuid(workspace_id)
    try:
        require_permission(
            session,
            user_id=context.user_id,
            workspace_id=workspace,
            permission=Permission.MANAGE_SECRETS,
            mfa_verified=context.mfa_verified,
        )
    except AuthorizationDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return app.credentials.put(
        session,
        workspace_id=workspace,
        actor_user_id=context.user_id,
        provider=provider,
        value=body.value,
    )


@router.get("/secrets", response_model=list[SecretStatusResponse])
def list_secrets(
    workspace_id: str,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    workspace = workspace_uuid(workspace_id)
    try:
        require_permission(
            session,
            user_id=context.user_id,
            workspace_id=workspace,
            permission=Permission.MANAGE_SECRETS,
            mfa_verified=context.mfa_verified,
        )
    except AuthorizationDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return app.credentials.list_status(session, workspace_id=workspace)
