from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...application.authentication import AuthContext
from ...application.authorization import AuthorizationDenied, require_permission
from ...domain.identity import Permission
from ...domain.privacy import WorkspacePrivacyPolicy
from ...infrastructure.models import UserModel
from ..dependencies import WebRuntime, current_auth, db_session, runtime, workspace_uuid
from ..schemas import (
    DataSubjectRequestBody,
    DataSubjectRequestResponse,
    PrivacyPolicyRequest,
    PrivacyPolicyResponse,
    SuppressionRequest,
)


router = APIRouter(prefix="/workspaces/{workspace_id}/privacy", tags=["privacy"])


def _require_admin(session, context, workspace_id):
    try:
        require_permission(
            session,
            user_id=context.user_id,
            workspace_id=workspace_id,
            permission=Permission.MANAGE_WORKSPACE,
            mfa_verified=context.mfa_verified,
        )
    except AuthorizationDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc


def _require_platform_admin_for_global(session, context, scope: str) -> None:
    if scope != "global":
        return
    user = session.get(UserModel, context.user_id)
    if user is None or not user.is_platform_admin or not context.mfa_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "La suppression globale richiede un amministratore di piattaforma con MFA.",
        )


@router.put("/policy", response_model=PrivacyPolicyResponse)
def put_policy(
    workspace_id: str,
    body: PrivacyPolicyRequest,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    workspace = workspace_uuid(workspace_id)
    _require_admin(session, context, workspace)
    if app.privacy_policies is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Servizio privacy non configurato.")
    try:
        policy = WorkspacePrivacyPolicy(workspace_id=workspace, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return app.privacy_policies.put(
        session, policy=policy, actor_user_id=context.user_id
    )


@router.post("/suppressions", status_code=status.HTTP_201_CREATED)
def create_suppression(
    workspace_id: str,
    body: SuppressionRequest,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    workspace = workspace_uuid(workspace_id)
    _require_admin(session, context, workspace)
    if app.suppression is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Servizio privacy non configurato.")
    _require_platform_admin_for_global(session, context, body.scope)
    try:
        record = app.suppression.suppress(
            session,
            workspace_id=workspace,
            kind=body.kind,
            value=body.value,
            scope=body.scope,
            reason=body.reason,
            actor_user_id=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return {"id": str(record.id), "scope": record.scope, "created": True}


@router.post("/data-subject-requests", response_model=DataSubjectRequestResponse)
def process_data_subject_request(
    workspace_id: str,
    body: DataSubjectRequestBody,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    workspace = workspace_uuid(workspace_id)
    _require_admin(session, context, workspace)
    if app.data_subject_requests is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Servizio privacy non configurato.")
    try:
        if body.request_kind == "access":
            data = app.data_subject_requests.subject_data(
                session,
                workspace_id=workspace,
                kind=body.identifier_kind,
                value=body.value,
            )
            request = app.data_subject_requests.record_access(
                session,
                request_id=body.request_id,
                workspace_id=workspace,
                actor_user_id=context.user_id,
                kind=body.identifier_kind,
                value=body.value,
            )
            return DataSubjectRequestResponse(
                request_id=request.id, status=request.status, data=data
            )
        if body.request_kind == "rectification":
            if not body.replacement_value:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "replacement_value obbligatorio.")
            request = app.data_subject_requests.rectify(
                session,
                request_id=body.request_id,
                workspace_id=workspace,
                actor_user_id=context.user_id,
                kind=body.identifier_kind,
                value=body.value,
                replacement_value=body.replacement_value,
            )
        else:
            _require_platform_admin_for_global(
                session, context, body.suppression_scope
            )
            request = app.data_subject_requests.erase_and_suppress(
                session,
                request_id=body.request_id,
                workspace_id=workspace,
                actor_user_id=context.user_id,
                kind=body.identifier_kind,
                value=body.value,
                scope=body.suppression_scope,
                request_kind=body.request_kind,
            )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return DataSubjectRequestResponse(
        request_id=request.id,
        status=request.status,
        deleted_count=request.deleted_count,
    )
