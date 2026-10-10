"""Single authorization boundary for protected execution and delivery."""
from sqlalchemy import select

from src.domain.feature_licenses import (
    FeatureAction, FeatureContext, FeatureStatus, LicenseError, LicenseScope, SubjectKind,
)
from src.domain.identity import ROLE_PERMISSIONS, Role
from src.infrastructure.models import UserModel, WorkspaceMembershipModel, WorkspaceModel


def principal_feature_context(session, *, user_id, workspace_id, installation_id,
                              mfa_verified, workspace_active):
    user = session.scalar(select(UserModel).where(UserModel.id == user_id)
                          .execution_options(populate_existing=True))
    member = session.scalar(select(WorkspaceMembershipModel).where(
        WorkspaceMembershipModel.user_id == user_id, WorkspaceMembershipModel.workspace_id == workspace_id)
        .execution_options(populate_existing=True))
    try:
        permissions = ROLE_PERMISSIONS[Role(member.role)] if member else frozenset()
    except ValueError:
        permissions = frozenset()
    return FeatureContext(
        LicenseScope(installation_id, SubjectKind.WORKSPACE_USER, user_id, workspace_id),
        permissions, mfa_verified,
        bool(user and user.is_active and member and workspace_active))


def server_feature_context(session, *, auth, workspace_id, installation_id):
    workspace = session.scalar(select(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
                               .execution_options(populate_existing=True))
    return principal_feature_context(session, user_id=auth.user_id, workspace_id=workspace_id,
        installation_id=installation_id, mfa_verified=auth.mfa_verified,
        workspace_active=bool(workspace and workspace.is_active))


class FeatureAccessService:
    def __init__(self, licenses, catalog):
        self.licenses, self.catalog = licenses, catalog

    def require(self, context, feature_id, *, action=FeatureAction.EXECUTE):
        if not context.principal_active or not isinstance(action, FeatureAction):
            raise LicenseError("feature_role_denied")
        feature = self.catalog.get(feature_id)
        claims = self.licenses.require_valid(context.scope)
        if feature_id not in claims.features:
            raise LicenseError("feature_not_granted")
        if context.scope.subject_kind is SubjectKind.WORKSPACE_USER:
            required = feature.execute_permissions if action is FeatureAction.EXECUTE else feature.view_permissions
            mfa = feature.execute_mfa if action is FeatureAction.EXECUTE else feature.view_mfa
            if not all(p in context.permissions for p in required) or (mfa and not context.mfa_verified):
                raise LicenseError("feature_role_denied")
        if feature.module_status != "available":
            raise LicenseError("feature_unavailable")
        return claims

    def list_status(self, context):
        summary = self.licenses.summary(context.scope)
        return tuple(FeatureStatus(item.feature_id, item.label,
            bool(context.principal_active and summary.license_status == "valid" and item.feature_id in summary.features),
            item.module_status, summary.license_status, summary.expires_at) for item in self.catalog.all())
