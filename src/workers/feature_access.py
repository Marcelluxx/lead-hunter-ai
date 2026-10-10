"""Contexts for future protected handlers, derived only from persisted job ownership."""
from sqlalchemy import select, text

from src.application.feature_access import principal_feature_context
from src.domain.feature_licenses import LicenseError
from src.infrastructure.models import JobModel, WorkspaceModel


def job_feature_context(session, *, job_id, installation_id):
    job = session.scalar(select(JobModel).where(JobModel.id == job_id).execution_options(populate_existing=True))
    if job is None:
        raise LicenseError("feature_role_denied")
    if session.bind.dialect.name == "postgresql":
        active = session.scalar(text("SELECT EXISTS (SELECT 1 FROM public.app_active_workspace_ids() "
                                     "WHERE workspace_id = :id)"), {"id": str(job.workspace_id)})
    else:
        workspace = session.get(WorkspaceModel, job.workspace_id)
        active = bool(workspace and workspace.is_active)
    return principal_feature_context(session, user_id=job.created_by, workspace_id=job.workspace_id,
        installation_id=installation_id, mfa_verified=False, workspace_active=active)
