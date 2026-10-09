"""Transactional grant replacement and an independently committed license clock."""
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.domain.feature_licenses import LicenseError, StoredGrant, SubjectKind, valid_epoch
from src.infrastructure.license_models import FeatureLicenseGrantModel, LicenseClockStateModel
from src.infrastructure.models import WorkspaceMembershipModel, utc_now


class SqlLicenseRepository:
    def __init__(self, session, installation_id):
        self.session, self.installation_id = session, installation_id

    def _check(self, scope):
        if scope.subject_kind is not SubjectKind.WORKSPACE_USER or scope.installation_id != self.installation_id:
            raise LicenseError("license_subject_mismatch")

    def _query(self, scope):
        return select(FeatureLicenseGrantModel).where(
            FeatureLicenseGrantModel.installation_id == scope.installation_id,
            FeatureLicenseGrantModel.workspace_id == scope.workspace_id,
            FeatureLicenseGrantModel.user_id == scope.subject_id)

    def _lock(self, scope):
        self._check(scope)
        # Lock a stable row even when no grant exists yet.
        member = self.session.scalar(select(WorkspaceMembershipModel).where(
            WorkspaceMembershipModel.workspace_id == scope.workspace_id,
            WorkspaceMembershipModel.user_id == scope.subject_id).with_for_update())
        if member is None:
            raise LicenseError("feature_role_denied")

    def read(self, scope):
        self._check(scope)
        try:
            row = self.session.scalar(self._query(scope).order_by(
                FeatureLicenseGrantModel.active.desc(), FeatureLicenseGrantModel.updated_at.desc(),
                FeatureLicenseGrantModel.id.desc()).execution_options(populate_existing=True).limit(1))
            if row is None:
                return None
            return StoredGrant(row.token, row.license_id, not row.active or row.revoked_at is not None)
        except SQLAlchemyError:
            raise LicenseError("license_storage_unavailable") from None

    def activate(self, scope, *, token, claims, actor_id=None):
        self._check(scope)
        if claims.scope != scope:
            raise LicenseError("license_subject_mismatch")
        try:
            self._lock(scope)
            old = self.session.scalar(select(FeatureLicenseGrantModel).where(
                FeatureLicenseGrantModel.license_id == claims.license_id).execution_options(populate_existing=True))
            if old is not None:
                if old.revoked_at is not None or not old.active:
                    raise LicenseError("license_revoked")
                if old.token != token or (old.workspace_id, old.user_id, old.installation_id) != (
                        scope.workspace_id, scope.subject_id, scope.installation_id):
                    raise LicenseError("license_invalid")
                return
            active = self.session.scalars(self._query(scope).where(
                FeatureLicenseGrantModel.active.is_(True)).execution_options(populate_existing=True)).all()
            for grant in active:
                grant.active = False
                grant.revoked_at = utc_now()
            self.session.flush()  # Free the partial unique index before inserting the replacement.
            self.session.add(FeatureLicenseGrantModel(
                license_id=claims.license_id, installation_id=scope.installation_id,
                workspace_id=scope.workspace_id, user_id=scope.subject_id, token=token,
                issued_at=claims.issued_at, not_before=claims.not_before, expires_at=claims.expires_at,
                features=list(claims.features), active=True, imported_by=actor_id))
            self.session.flush()
        except SQLAlchemyError:
            raise LicenseError("license_storage_unavailable") from None

    def revoke(self, scope, *, license_id, actor_id=None):
        try:
            self._lock(scope)
            grant = self.session.scalar(self._query(scope).where(
                FeatureLicenseGrantModel.license_id == license_id).execution_options(populate_existing=True))
            if grant is not None and grant.revoked_at is None:
                grant.active, grant.revoked_at = False, utc_now()
                self.session.flush()
        except SQLAlchemyError:
            raise LicenseError("license_storage_unavailable") from None


class PostgresClockStore:
    def __init__(self, database, installation_id):
        self.database, self.installation_id = database, installation_id

    def advance(self, observed_epoch):
        if not valid_epoch(observed_epoch):
            raise LicenseError("license_clock_regression")
        try:
            with self.database.session() as session:
                if self.database.engine.dialect.name == "postgresql":
                    session.execute(text("SELECT set_config('app.installation_id', :id, true)"),
                                    {"id": str(self.installation_id)})
                    return session.scalar(text("SELECT public.app_advance_license_clock(:id, :epoch)"),
                                          {"id": str(self.installation_id), "epoch": observed_epoch})
                # SQLite is used only by unit fixtures, not as a server substitute.
                statement = sqlite_insert(LicenseClockStateModel).values(
                    installation_id=self.installation_id, maximum_epoch=observed_epoch)
                statement = statement.on_conflict_do_update(
                    index_elements=[LicenseClockStateModel.installation_id],
                    set_={"maximum_epoch": text("max(license_clock_state.maximum_epoch, excluded.maximum_epoch)")})
                session.execute(statement)
                return session.scalar(select(LicenseClockStateModel.maximum_epoch).where(
                    LicenseClockStateModel.installation_id == self.installation_id))
        except SQLAlchemyError:
            raise LicenseError("license_storage_unavailable") from None
