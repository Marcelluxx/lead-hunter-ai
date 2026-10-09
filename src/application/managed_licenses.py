"""Authenticated administration imports signatures; admins cannot mint entitlements."""
from src.application.audit_log import append_audit_event
from src.application.feature_access import server_feature_context
from src.domain.feature_licenses import LicenseError, LicenseScope, SubjectKind
from src.domain.identity import Permission
from src.application.authentication import AuthContext


class ManagedLicenseService:
    def __init__(self, licenses):
        self.licenses = licenses

    def _scope(self, session, *, actor, workspace_id, user_id, installation_id, manage):
        context = server_feature_context(session, auth=actor, workspace_id=workspace_id,
                                         installation_id=installation_id)
        if not context.principal_active:
            raise LicenseError("feature_role_denied")
        if manage or actor.user_id != user_id:
            if Permission.MANAGE_WORKSPACE not in context.permissions or not context.mfa_verified:
                raise LicenseError("feature_role_denied")
        target = server_feature_context(session,
            auth=AuthContext(user_id, actor.session_id, False), workspace_id=workspace_id,
            installation_id=installation_id)
        if not target.principal_active:
            raise LicenseError("feature_role_denied")
        return LicenseScope(installation_id, SubjectKind.WORKSPACE_USER, user_id, workspace_id)

    def _audit(self, session, action, summary, actor):
        append_audit_event(session, action=action, workspace_id=summary.scope.workspace_id,
            actor_user_id=actor.user_id, target_type="feature_license", target_id=str(summary.license_id),
            details={"license_id": str(summary.license_id), "features": ",".join(summary.features),
                     "expires_at": summary.expires_at})

    def import_for_user(self, session, *, actor, workspace_id, user_id, installation_id, token):
        scope = self._scope(session, actor=actor, workspace_id=workspace_id, user_id=user_id,
                            installation_id=installation_id, manage=True)
        before = self.licenses.summary(scope)
        summary = self.licenses.import_license(scope, token, actor_id=actor.user_id)
        if before.license_id != summary.license_id:
            self._audit(session, "license.renewed" if before.license_id else "license.imported", summary, actor)
        return summary

    def revoke_for_user(self, session, *, actor, workspace_id, user_id, installation_id, license_id):
        scope = self._scope(session, actor=actor, workspace_id=workspace_id, user_id=user_id,
                            installation_id=installation_id, manage=True)
        before = self.licenses.summary(scope)
        summary = self.licenses.revoke_license(scope, license_id, actor_id=actor.user_id)
        if before.license_id == license_id and before.license_status != "revoked" and summary.license_status == "revoked":
            self._audit(session, "license.revoked", summary, actor)
        return summary

    def status_for_user(self, session, *, actor, workspace_id, user_id, installation_id):
        scope = self._scope(session, actor=actor, workspace_id=workspace_id, user_id=user_id,
                            installation_id=installation_id, manage=False)
        return self.licenses.summary(scope)
