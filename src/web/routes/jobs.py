from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...application.authentication import AuthContext
from ...application.authorization import AuthorizationDenied, require_permission
from ...application.budgets import BudgetExceeded
from ...domain.identity import Permission
from ...infrastructure.models import JobModel
from ..dependencies import WebRuntime, current_auth, db_session, runtime, workspace_uuid, commercial_execution, commercial_results
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
        result = app.jobs.create_commercial(
            session,
            workspace_id=workspace,
            auth=context,
            kind=body.kind,
            parameters=body.parameters,
            idempotency_key=idempotency_key,
            prices=app.job_prices,
            execution=commercial_execution(app),
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
    app: WebRuntime = Depends(runtime),
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
    return JobResponse(**commercial_results(app).status(job_id=job_uuid, workspace_id=workspace, auth=context))


@router.get('/{job_id}/results')
def get_results(workspace_id: str, job_id: str, context: AuthContext = Depends(current_auth),
                app: WebRuntime = Depends(runtime)):
    content = commercial_results(app).render_results(job_id=workspace_uuid(job_id),
        workspace_id=workspace_uuid(workspace_id), auth=context)
    return Response(content, media_type='application/json', headers={'Cache-Control': 'no-store'})


@router.get('/{job_id}/export')
def export_results(workspace_id: str, job_id: str, context: AuthContext = Depends(current_auth),
                   app: WebRuntime = Depends(runtime)):
    service = commercial_results(app)
    identifiers = {'job_id': workspace_uuid(job_id), 'workspace_id': workspace_uuid(workspace_id), 'auth': context}
    content, media_type, permission, snapshot = service.export(**identifiers)
    extension = 'zip' if media_type == 'application/zip' else 'xlsx'
    return StreamingResponse(service.stream(content, permission=permission, snapshot=snapshot, **identifiers), media_type=media_type,
        headers={'Cache-Control': 'no-store', 'Content-Disposition': f'attachment; filename="{job_id}.{extension}"'})


@router.post('/{job_id}/cancel', response_model=JobResponse)
def cancel_job(workspace_id: str, job_id: str, context: AuthContext = Depends(current_auth),
               app: WebRuntime = Depends(runtime)):
    identifiers = {'job_id': workspace_uuid(job_id), 'workspace_id': workspace_uuid(workspace_id), 'auth': context}
    commercial_execution(app).cancel(**identifiers)
    return JobResponse(**commercial_results(app).status(**identifiers))


@router.post('/{job_id}/resume', response_model=JobResponse, status_code=202)
def resume_job(workspace_id: str, job_id: str, context: AuthContext = Depends(current_auth),
               app: WebRuntime = Depends(runtime)):
    identifiers = {'job_id': workspace_uuid(job_id), 'workspace_id': workspace_uuid(workspace_id), 'auth': context}
    commercial_execution(app).resume(**identifiers)
    return JobResponse(**commercial_results(app).status(**identifiers))
