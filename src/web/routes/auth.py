from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ...application.authentication import AuthContext, AuthenticationError
from ..dependencies import WebRuntime, current_auth, db_session, runtime
from ..schemas import (
    LoginRequest,
    MfaCodeRequest,
    MfaEnrollmentResponse,
    TokenResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(response: Response, session_id: str, refresh: str, csrf: str) -> None:
    common = {"secure": True, "samesite": "lax", "path": "/auth"}
    response.set_cookie("lh_session", session_id, httponly=True, **common)
    response.set_cookie("lh_refresh", refresh, httponly=True, **common)
    response.set_cookie("lh_csrf", csrf, httponly=False, **common)


def _token_response(tokens) -> TokenResponse:
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    if app.rate_limiter is not None:
        app.rate_limiter.require(
            scope="login",
            subject=request.client.host if request.client else "unknown",
            limit=10,
            window_seconds=60,
        )
    try:
        tokens = app.authentication.login(session, email=body.email, password=body.password)
        context = app.authentication.authenticate_access_token(session, tokens.access_token)
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    _set_session_cookies(response, str(context.session_id), tokens.refresh_token, tokens.csrf_token)
    return _token_response(tokens)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    x_csrf_token: str = Header(default=""),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    if app.rate_limiter is not None:
        app.rate_limiter.require(
            scope="refresh",
            subject=request.client.host if request.client else "unknown",
            limit=30,
            window_seconds=60,
        )
    session_cookie = request.cookies.get("lh_session", "")
    refresh_cookie = request.cookies.get("lh_refresh", "")
    csrf_cookie = request.cookies.get("lh_csrf", "")
    if not x_csrf_token or not secrets.compare_digest(x_csrf_token, csrf_cookie):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF non valido.")
    try:
        session_id = uuid.UUID(session_cookie)
        tokens = app.authentication.refresh(
            session,
            session_id=session_id,
            refresh_token=refresh_cookie,
            csrf_token=x_csrf_token,
        )
        context = app.authentication.authenticate_access_token(session, tokens.access_token)
    except (ValueError, AuthenticationError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessione non valida.") from exc
    _set_session_cookies(response, str(context.session_id), tokens.refresh_token, tokens.csrf_token)
    return _token_response(tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    app.authentication.logout(session, context=context)
    for name in ("lh_session", "lh_refresh", "lh_csrf"):
        response.delete_cookie(name, path="/auth", secure=True, samesite="lax")


@router.post("/mfa/enrollment", response_model=MfaEnrollmentResponse)
def begin_mfa(
    request: Request,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    if app.rate_limiter is not None:
        app.rate_limiter.require(
            scope="mfa",
            subject=f"{context.user_id}:{request.client.host if request.client else 'unknown'}",
            limit=10,
            window_seconds=300,
        )
    try:
        enrollment = app.authentication.begin_mfa_enrollment(session, context=context)
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return MfaEnrollmentResponse(
        provisioning_uri=enrollment.provisioning_uri,
        recovery_codes=list(enrollment.recovery_codes),
    )


@router.post("/mfa/confirm", response_model=TokenResponse)
def confirm_mfa(
    body: MfaCodeRequest,
    request: Request,
    response: Response,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    if app.rate_limiter is not None:
        app.rate_limiter.require(
            scope="mfa",
            subject=f"{context.user_id}:{request.client.host if request.client else 'unknown'}",
            limit=10,
            window_seconds=300,
        )
    try:
        tokens = app.authentication.confirm_mfa(session, context=context, code=body.code)
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    _set_session_cookies(response, str(context.session_id), tokens.refresh_token, tokens.csrf_token)
    return _token_response(tokens)


@router.post("/mfa/verify", response_model=TokenResponse)
def verify_mfa(
    body: MfaCodeRequest,
    request: Request,
    response: Response,
    context: AuthContext = Depends(current_auth),
    session: Session = Depends(db_session),
    app: WebRuntime = Depends(runtime),
):
    if app.rate_limiter is not None:
        app.rate_limiter.require(
            scope="mfa",
            subject=f"{context.user_id}:{request.client.host if request.client else 'unknown'}",
            limit=10,
            window_seconds=300,
        )
    try:
        tokens = app.authentication.verify_mfa(session, context=context, code=body.code)
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    _set_session_cookies(response, str(context.session_id), tokens.refresh_token, tokens.csrf_token)
    return _token_response(tokens)
