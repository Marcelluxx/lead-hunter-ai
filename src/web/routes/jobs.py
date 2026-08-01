from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...application.authentication import AuthContext
from ...application.authorization import AuthorizationDenied, require_permission
from ...application.budgets import BudgetExceeded
from ...domain.identity import Permission
from ...infrastructure.models import JobModel
from ..dependencies import WebRuntime, current_auth, db_session, runtime, workspace_uuid
from ..schemas import JobCreateRequest, JobResponse


router = APIRouter(prefix="/workspaces/{workspace_id}/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    workspace_id: str,
    body: JobCreateRequest,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
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
            permission=Permission.START_JOB,
            mfa_verified=context.mfa_verified,
        )
        if app.rate_limiter is not None:
            app.rate_limiter.require(
                scope="job-create",
                subject=f"{workspace}:{context.user_id}",
                limit=20,
                window_seconds=60,
            )
        result = app.jobs.create(
            session,
            workspace_id=workspace,
            user_id=context.user_id,
            kind=body.kind,
            parameters=body.parameters,
            estimated_cost=body.estimated_cost,
            idempotency_key=idempotency_key,
        )
    except AuthorizationDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except BudgetExceeded as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return JobResponse(id=result.job.id, state=result.job.state, created=result.created)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    workspace_id: str,
    job_id: str,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
):
    workspace = workspace_uuid(workspace_id)
    job_uuid = workspace_uuid(job_id)
    try:
        require_permission(
            session,
            user_id=context.user_id,
            workspace_id=workspace,
            permission=Permission.VIEW_RESULTS,
            mfa_verified=context.mfa_verified,
        )
    except AuthorizationDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    job = session.scalar(
        select(JobModel).where(JobModel.id == job_uuid, JobModel.workspace_id == workspace)
    )
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job non trovato.")
    return JobResponse(id=job.id, state=job.state)
