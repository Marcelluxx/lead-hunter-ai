import unittest
from dataclasses import replace
from uuid import uuid4

from sqlalchemy import delete, select, text
from sqlalchemy.exc import ProgrammingError

from src.infrastructure.license_models import FeatureLicenseGrantModel, LicenseClockStateModel
from src.infrastructure.license_repository import SqlLicenseRepository, PostgresClockStore
from src.infrastructure.models import UserModel, WorkspaceModel
from tests.integration.postgres_helpers import POSTGRES_AVAILABLE, databases
from tests.license_helpers import license_claims, seed_license_subject


@unittest.skipUnless(POSTGRES_AVAILABLE, 'PostgreSQL integration URLs not configured')
class FeatureLicenseRlsTests(unittest.TestCase):
    def setUp(self):
        self.owner, self.app, self.worker = databases()
        self.scope = seed_license_subject(self.owner)
        self.other = seed_license_subject(self.owner)

    def tearDown(self):
        with self.owner.session() as session:
            for scope in (self.scope, self.other):
                session.execute(delete(WorkspaceModel).where(WorkspaceModel.id == scope.workspace_id))
                session.execute(delete(UserModel).where(UserModel.id == scope.subject_id))
                session.execute(delete(LicenseClockStateModel).where(LicenseClockStateModel.installation_id == scope.installation_id))
        for database in (self.owner, self.app, self.worker):
            database.engine.dispose()

    def activate(self, database, scope, claims=None):
        with database.session(scope.workspace_id) as session:
            SqlLicenseRepository(session, scope.installation_id).activate(
                scope, claims=claims or license_claims(scope=scope, features=('export.no_website',)),
                token='integration-token', actor_id=scope.subject_id)

    def test_grants_are_workspace_scoped_and_worker_read_only(self):
        self.activate(self.app, self.scope, replace(license_claims(scope=self.scope), license_id=uuid4()))
        self.activate(self.app, self.other, replace(license_claims(scope=self.other), license_id=uuid4()))
        with self.app.session() as session:
            self.assertEqual(session.scalars(select(FeatureLicenseGrantModel)).all(), [])
        with self.app.session(self.scope.workspace_id) as session:
            self.assertIsNone(SqlLicenseRepository(session, self.other.installation_id).read(self.other))
        with self.worker.session(self.scope.workspace_id) as session:
            self.assertIsNotNone(SqlLicenseRepository(session, self.scope.installation_id).read(self.scope))
        with self.assertRaises(ProgrammingError), self.worker.session(self.scope.workspace_id) as session:
            session.add(self.raw_grant(self.scope))
            session.flush()
        with self.assertRaises(ProgrammingError), self.app.session(self.scope.workspace_id) as session:
            session.execute(text("DELETE FROM feature_license_grants"))
        with self.assertRaises(ProgrammingError), self.app.session(self.scope.workspace_id) as session:
            session.add(self.raw_grant(self.other))
            session.flush()

    def raw_grant(self, scope):
        return FeatureLicenseGrantModel(license_id=uuid4(), installation_id=scope.installation_id,
            workspace_id=scope.workspace_id, user_id=scope.subject_id, token='integration-token',
            issued_at=0, not_before=0, expires_at=100, features=['diagnostics.full'], active=False)

    def test_license_time_only_advances(self):
        for database in (self.app, self.worker):
            clock = PostgresClockStore(database, self.scope.installation_id)
            self.assertEqual(clock.advance(1000), 1000)
            self.assertEqual(clock.advance(800), 1000)
            with self.assertRaises(ProgrammingError), database.session() as session:
                session.execute(text("UPDATE license_clock_state SET maximum_epoch = 0"))
            with self.assertRaises(ProgrammingError), database.session() as session:
                session.execute(text("SELECT public.app_advance_license_clock(:id, 1)"),
                                {'id': str(self.scope.installation_id)})
