"""Revocable local authentication, MFA and explicit OIDC identity mapping."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pyotp
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..infrastructure.crypto import (
    AccessTokenService,
    PasswordService,
    SecretCipher,
    TokenClaims,
    hash_opaque_token,
    new_opaque_token,
)
from ..infrastructure.models import (
    MfaCredentialModel,
    OidcIdentityModel,
    SessionModel,
    UserModel,
)
from .audit_log import append_audit_event


class AuthenticationError(PermissionError):
    pass


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    csrf_token: str
    expires_in: int


@dataclass(frozen=True)
class AuthContext:
    user_id: uuid.UUID
    session_id: uuid.UUID
    mfa_verified: bool


@dataclass(frozen=True)
class MfaEnrollment:
    provisioning_uri: str
    recovery_codes: tuple[str, ...]


class AuthenticationService:
    def __init__(
        self,
        *,
        passwords: PasswordService,
        tokens: AccessTokenService,
        cipher: SecretCipher,
        refresh_lifetime: timedelta = timedelta(days=30),
        access_lifetime_seconds: int = 900,
    ):
        self._passwords = passwords
        self._tokens = tokens
        self._cipher = cipher
        self._refresh_lifetime = refresh_lifetime
        self._access_lifetime_seconds = access_lifetime_seconds

    def login(self, session: Session, *, email: str, password: str) -> AuthTokens:
        normalized = email.strip().casefold()
        user = session.scalar(select(UserModel).where(UserModel.email == normalized))
        valid = self._passwords.verify(password, user.password_hash if user else None)
        if user is None or not valid or not user.is_active:
            append_audit_event(session, action="auth.login_failed", details={"result": "denied"})
            raise AuthenticationError("Credenziali non valide.")
        result = self._create_session(session, user=user, mfa_verified=False)
        append_audit_event(
            session,
            action="auth.login",
            actor_user_id=user.id,
            target_type="session",
            target_id=str(result[0].id),
            details={"result": "success"},
        )
        return result[1]

    def refresh(
        self,
        session: Session,
        *,
        session_id: uuid.UUID,
        refresh_token: str,
        csrf_token: str,
    ) -> AuthTokens:
        record = session.get(SessionModel, session_id)
        now = datetime.now(timezone.utc)
        if (
            record is None
            or record.revoked_at is not None
            or _as_utc(record.expires_at) <= now
        ):
            raise AuthenticationError("Sessione non valida.")
        if (
            not secrets.compare_digest(record.refresh_token_hash, hash_opaque_token(refresh_token))
            or not secrets.compare_digest(record.csrf_token_hash, hash_opaque_token(csrf_token))
        ):
            # Persist replay revocation independently of the HTTP 401 rollback.
            record.revoked_at = now
            session.commit()
            raise AuthenticationError("Sessione non valida.")
        user = session.get(UserModel, record.user_id)
        if user is None or not user.is_active:
            record.revoked_at = now
            raise AuthenticationError("Sessione non valida.")
        return self._rotate(session, record=record, user=user)

    def authenticate_access_token(self, session: Session, token: str) -> AuthContext:
        claims: TokenClaims = self._tokens.decode(token)
        try:
            user_id = uuid.UUID(claims.user_id)
            session_id = uuid.UUID(claims.session_id)
        except ValueError as exc:
            raise AuthenticationError("Sessione non valida.") from exc
        record = session.get(SessionModel, session_id)
        user = session.get(UserModel, user_id)
        now = datetime.now(timezone.utc)
        if (
            record is None
            or user is None
            or record.user_id != user_id
            or record.revoked_at is not None
            or _as_utc(record.expires_at) <= now
            or not user.is_active
            or claims.session_version != user.session_version
            or claims.mfa_verified != record.mfa_verified
        ):
            raise AuthenticationError("Sessione non valida.")
        record.last_seen_at = now
        return AuthContext(user_id=user_id, session_id=session_id, mfa_verified=record.mfa_verified)

    def logout(self, session: Session, *, context: AuthContext) -> None:
        record = session.get(SessionModel, context.session_id)
        if record is not None and record.user_id == context.user_id:
            record.revoked_at = datetime.now(timezone.utc)
        append_audit_event(
            session,
            action="auth.logout",
            actor_user_id=context.user_id,
            target_type="session",
            target_id=str(context.session_id),
        )

    def revoke_all(self, session: Session, *, user_id: uuid.UUID) -> None:
        user = session.get(UserModel, user_id)
        if user is None:
            return
        user.session_version += 1
        session.execute(
            update(SessionModel)
            .where(SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    def begin_mfa_enrollment(
        self, session: Session, *, context: AuthContext
    ) -> MfaEnrollment:
        user_id = context.user_id
        user = session.get(UserModel, user_id)
        if user is None:
            raise AuthenticationError("Utente non valido.")
        current = session.get(MfaCredentialModel, user_id)
        if current is not None and current.confirmed_at is not None and not context.mfa_verified:
            raise AuthenticationError("MFA corrente richiesta per riconfigurare MFA.")
        secret = pyotp.random_base32()
        codes = tuple(secrets.token_urlsafe(12) for _ in range(8))
        associated_data = f"mfa:{user_id}:v1"
        credential = current
        values = {
            "secret_ciphertext": self._cipher.encrypt(secret, associated_data=associated_data),
            "recovery_code_hashes": [hash_opaque_token(code) for code in codes],
            "confirmed_at": None,
        }
        if credential is None:
            credential = MfaCredentialModel(user_id=user_id, **values)
            session.add(credential)
        else:
            for name, value in values.items():
                setattr(credential, name, value)
        session.flush()
        return MfaEnrollment(
            provisioning_uri=pyotp.TOTP(secret).provisioning_uri(
                name=user.email,
                issuer_name="Lead Hunter",
            ),
            recovery_codes=codes,
        )

    def confirm_mfa(self, session: Session, *, context: AuthContext, code: str) -> AuthTokens:
        credential = self._verified_mfa_credential(session, context.user_id, code)
        credential.confirmed_at = datetime.now(timezone.utc)
        record = session.get(SessionModel, context.session_id)
        user = session.get(UserModel, context.user_id)
        if record is None or user is None or record.revoked_at is not None:
            raise AuthenticationError("Sessione non valida.")
        record.mfa_verified = True
        append_audit_event(session, action="auth.mfa_confirmed", actor_user_id=user.id)
        return self._rotate(session, record=record, user=user)

    def verify_mfa(self, session: Session, *, context: AuthContext, code: str) -> AuthTokens:
        credential = self._verified_mfa_credential(session, context.user_id, code)
        if credential.confirmed_at is None:
            raise AuthenticationError("MFA non ancora confermata.")
        record = session.get(SessionModel, context.session_id)
        user = session.get(UserModel, context.user_id)
        if record is None or user is None or record.revoked_at is not None:
            raise AuthenticationError("Sessione non valida.")
        record.mfa_verified = True
        return self._rotate(session, record=record, user=user)

    def map_oidc_identity(
        self,
        session: Session,
        *,
        provider: str,
        subject: str,
        user_id: uuid.UUID,
    ) -> OidcIdentityModel:
        if session.get(UserModel, user_id) is None:
            raise AuthenticationError("Utente locale non valido.")
        existing = session.scalar(
            select(OidcIdentityModel).where(
                OidcIdentityModel.provider == provider,
                OidcIdentityModel.subject == subject,
            )
        )
        if existing is not None and existing.user_id != user_id:
            raise AuthenticationError("Identita OIDC gia associata.")
        if existing is None:
            existing = OidcIdentityModel(provider=provider, subject=subject, user_id=user_id)
            session.add(existing)
        return existing

    def _verified_mfa_credential(
        self, session: Session, user_id: uuid.UUID, code: str
    ) -> MfaCredentialModel:
        credential = session.get(MfaCredentialModel, user_id)
        if credential is None:
            raise AuthenticationError("MFA non configurata.")
        secret = self._cipher.decrypt(
            credential.secret_ciphertext,
            associated_data=f"mfa:{user_id}:v1",
        )
        if pyotp.TOTP(secret).verify(code, valid_window=1):
            return credential
        code_hash = hash_opaque_token(code)
        if code_hash in credential.recovery_code_hashes:
            credential.recovery_code_hashes = [
                item for item in credential.recovery_code_hashes if item != code_hash
            ]
            return credential
        raise AuthenticationError("Codice MFA non valido.")

    def _create_session(
        self, session: Session, *, user: UserModel, mfa_verified: bool
    ) -> tuple[SessionModel, AuthTokens]:
        refresh = new_opaque_token()
        csrf = new_opaque_token()
        now = datetime.now(timezone.utc)
        record = SessionModel(
            user_id=user.id,
            refresh_token_hash=hash_opaque_token(refresh),
            csrf_token_hash=hash_opaque_token(csrf),
            mfa_verified=mfa_verified,
            expires_at=now + self._refresh_lifetime,
        )
        session.add(record)
        session.flush()
        return record, self._token_bundle(user, record, refresh, csrf)

    def _rotate(self, session: Session, *, record: SessionModel, user: UserModel) -> AuthTokens:
        refresh = new_opaque_token()
        csrf = new_opaque_token()
        record.refresh_token_hash = hash_opaque_token(refresh)
        record.csrf_token_hash = hash_opaque_token(csrf)
        record.last_seen_at = datetime.now(timezone.utc)
        session.flush()
        return self._token_bundle(user, record, refresh, csrf)

    def _token_bundle(
        self, user: UserModel, record: SessionModel, refresh: str, csrf: str
    ) -> AuthTokens:
        access = self._tokens.issue(
            user_id=str(user.id),
            session_id=str(record.id),
            session_version=user.session_version,
            mfa_verified=record.mfa_verified,
        )
        return AuthTokens(access, refresh, csrf, self._access_lifetime_seconds)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
