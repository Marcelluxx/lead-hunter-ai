from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..application.authentication import (
    AuthContext,
    AuthenticationError,
    AuthenticationService,
)
from ..application.budgets import BudgetService
from ..application.jobs import JobService
from ..application.secrets import CredentialService
from ..application.data_subject_requests import DataSubjectRequestService
from ..application.privacy_policy import WorkspacePrivacyPolicyService
from ..application.suppression import SuppressionService
from ..infrastructure.database import Database


@dataclass(frozen=True)
class WebRuntime:
    database: Database
    authentication: AuthenticationService
    jobs: JobService
    budgets: BudgetService
    credentials: CredentialService
    rate_limiter: object | None = None
    privacy_policies: WorkspacePrivacyPolicyService | None = None
    suppression: SuppressionService | None = None
    data_subject_requests: DataSubjectRequestService | None = None


_bearer = HTTPBearer(auto_error=False)


def runtime(request: Request) -> WebRuntime:
    return request.app.state.runtime


def db_session(
    request: Request, app: WebRuntime = Depends(runtime)
) -> Iterator[Session]:
    workspace_value = request.path_params.get("workspace_id")
    workspace_id = workspace_uuid(workspace_value) if workspace_value else None
    with app.database.session(workspace_id=workspace_id) as session:
        yield session


def current_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
) -> AuthContext:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticazione richiesta.")
    try:
        return app.authentication.authenticate_access_token(session, credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


def workspace_uuid(workspace_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(workspace_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace non trovato.") from exc
