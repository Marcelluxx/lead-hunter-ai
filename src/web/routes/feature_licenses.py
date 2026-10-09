from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.application.authentication import AuthContext
from src.application.feature_access import server_feature_context
from src.domain.feature_licenses import LicenseError
from src.infrastructure.models import UserModel, WorkspaceMembershipModel, WorkspaceModel
from src.licensing.catalog import FeatureCatalog
from src.settings import SettingsError
from src.web.dependencies import WebRuntime, current_auth, db_session, runtime, request_license_services
from src.web.schemas import FeatureStatusResponse, LicenseImportRequest, LicenseSummaryResponse

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["feature-licenses"])


def public_summary(summary):
    scope = summary.scope
    return LicenseSummaryResponse(license_id=summary.license_id, installation_id=scope.installation_id,
        subject_kind=scope.subject_kind.value, subject_id=scope.subject_id, workspace_id=scope.workspace_id,
        license_status=summary.license_status, not_before=utc_date(summary.not_before),
        expires_at=utc_date(summary.expires_at), features=summary.features)


def utc_date(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc) if epoch is not None else None


def license_http_error(error, *, importing=False):
    code = error.code if isinstance(error, LicenseError) else "license_storage_unavailable"
    status = 503 if code == "license_storage_unavailable" else (
        422 if importing and code in {"license_invalid", "license_subject_mismatch", "license_expired",
                                    "license_not_yet_valid", "license_revoked"} else 403)
    return HTTPException(status, code)


def require_member(session, auth, workspace_id):
    user = session.get(UserModel, auth.user_id)
    workspace = session.get(WorkspaceModel, workspace_id)
    member = session.scalar(select(WorkspaceMembershipModel).where(
        WorkspaceMembershipModel.user_id == auth.user_id, WorkspaceMembershipModel.workspace_id == workspace_id))
    if not user or not user.is_active or not workspace or not workspace.is_active or not member:
        raise HTTPException(403, "feature_role_denied")


@router.get("/features", response_model=list[FeatureStatusResponse])
def features(workspace_id: UUID, auth: AuthContext = Depends(current_auth),
             session: Session = Depends(db_session), app: WebRuntime = Depends(runtime)):
    require_member(session, auth, workspace_id)
    settings = app.license_settings
    if settings is None or settings.trust_file is None:
        return [FeatureStatusResponse(feature_id=f.feature_id, label=f.label, granted=False,
                module_status=f.module_status, license_status="missing", expires_at=None)
                for f in (app.feature_catalog or FeatureCatalog()).all()]
    try:
        _, access, _ = request_license_services(session, app)
        context = server_feature_context(session, auth=auth, workspace_id=workspace_id,
                                        installation_id=settings.installation_id)
        return [FeatureStatusResponse(**{**asdict(f), "expires_at": utc_date(f.expires_at)})
                for f in access.list_status(context)]
    except (LicenseError, SettingsError) as error:
        raise license_http_error(error) from None


@router.put("/feature-licenses/{user_id}", response_model=LicenseSummaryResponse)
def import_license(workspace_id: UUID, user_id: UUID, body: LicenseImportRequest,
                   auth: AuthContext = Depends(current_auth), session: Session = Depends(db_session),
                   app: WebRuntime = Depends(runtime)):
    require_member(session, auth, workspace_id)
    try:
        _, _, managed = request_license_services(session, app)
        return public_summary(managed.import_for_user(session, actor=auth, workspace_id=workspace_id,
            user_id=user_id, installation_id=app.license_settings.installation_id, token=body.token))
    except (LicenseError, SettingsError) as error:
        raise license_http_error(error, importing=True) from None


@router.get("/feature-licenses/{user_id}", response_model=LicenseSummaryResponse)
def status(workspace_id: UUID, user_id: UUID, auth: AuthContext = Depends(current_auth),
           session: Session = Depends(db_session), app: WebRuntime = Depends(runtime)):
    require_member(session, auth, workspace_id)
    try:
        _, _, managed = request_license_services(session, app)
        return public_summary(managed.status_for_user(session, actor=auth, workspace_id=workspace_id,
            user_id=user_id, installation_id=app.license_settings.installation_id))
    except (LicenseError, SettingsError) as error:
        raise license_http_error(error) from None


@router.delete("/feature-licenses/{user_id}/{license_id}", response_model=LicenseSummaryResponse)
def revoke(workspace_id: UUID, user_id: UUID, license_id: UUID, auth: AuthContext = Depends(current_auth),
           session: Session = Depends(db_session), app: WebRuntime = Depends(runtime)):
    require_member(session, auth, workspace_id)
    try:
        _, _, managed = request_license_services(session, app)
        return public_summary(managed.revoke_for_user(session, actor=auth, workspace_id=workspace_id,
            user_id=user_id, installation_id=app.license_settings.installation_id, license_id=license_id))
    except (LicenseError, SettingsError) as error:
        raise license_http_error(error) from None
