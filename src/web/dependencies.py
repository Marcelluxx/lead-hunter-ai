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
from ..licensing.settings import LicenseSettings
from ..licensing.catalog import FeatureCatalog


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
    license_settings: LicenseSettings | None = None
    feature_catalog: FeatureCatalog | None = None


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


def request_license_services(session: Session, app: WebRuntime):
    from ..application.feature_licenses import LicenseService
    from ..application.feature_access import FeatureAccessService
    from ..application.managed_licenses import ManagedLicenseService
    from ..application.license_clock import GuardedClock, SystemClock
    from ..domain.feature_licenses import LicenseError
    from ..infrastructure.license_repository import SqlLicenseRepository, PostgresClockStore
    from ..licensing.verification import LicenseVerifier
    settings = app.license_settings
    if settings is None or settings.trust_file is None or settings.installation_id is None:
        raise LicenseError("license_storage_unavailable")
    catalog = app.feature_catalog or FeatureCatalog()
    licenses = LicenseService(SqlLicenseRepository(session, settings.installation_id),
        LicenseVerifier(settings.load_trusted_keys(), catalog),
        GuardedClock(SystemClock(), PostgresClockStore(app.database, settings.installation_id)))
    return licenses, FeatureAccessService(licenses, catalog), ManagedLicenseService(licenses)
