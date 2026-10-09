import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import uuid4

from sqlalchemy import delete, select

from src.domain.feature_licenses import LicenseError
from src.infrastructure.license_models import FeatureLicenseGrantModel
from src.infrastructure.license_repository import SqlLicenseRepository
from src.infrastructure.models import UserModel, WorkspaceModel
from tests.integration.postgres_helpers import POSTGRES_AVAILABLE, databases
from tests.license_helpers import license_claims, seed_license_subject


@unittest.skipUnless(POSTGRES_AVAILABLE, 'PostgreSQL integration URLs not configured')
class FeatureLicenseConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.owner, self.app, self.worker = databases()
        self.scope = seed_license_subject(self.owner)

    def tearDown(self):
        with self.owner.session() as session:
            session.execute(delete(WorkspaceModel).where(WorkspaceModel.id == self.scope.workspace_id))
            session.execute(delete(UserModel).where(UserModel.id == self.scope.subject_id))
        for database in (self.owner, self.app, self.worker):
            database.engine.dispose()

    def write(self, claims):
        with self.app.session(self.scope.workspace_id) as session:
            SqlLicenseRepository(session, self.scope.installation_id).activate(
                self.scope, token=str(claims.license_id), claims=claims, actor_id=self.scope.subject_id)

    def rows(self):
        with self.owner.session() as session:
            return session.scalars(select(FeatureLicenseGrantModel).where(
                FeatureLicenseGrantModel.workspace_id == self.scope.workspace_id)).all()

    def test_concurrent_renewals_have_one_active_grant(self):
        claims = [replace(license_claims(scope=self.scope), license_id=uuid4()) for _ in range(2)]
        barrier = Barrier(2)
        def run(item):
            barrier.wait(timeout=10)
            self.write(item)
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(run, claims))
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(row.active for row in rows), 1)
        self.assertEqual(sum(row.revoked_at is not None for row in rows), 1)

    def test_revoke_and_renew_preserve_tombstones(self):
        old = replace(license_claims(scope=self.scope), license_id=uuid4())
        newer = replace(old, license_id=uuid4())
        self.write(old)
        barrier = Barrier(2)
        def revoke():
            barrier.wait(timeout=10)
            with self.app.session(self.scope.workspace_id) as session:
                SqlLicenseRepository(session, self.scope.installation_id).revoke(
                    self.scope, license_id=old.license_id, actor_id=self.scope.subject_id)
        def renew():
            barrier.wait(timeout=10)
            self.write(newer)
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(revoke), pool.submit(renew)]
            for future in futures:
                future.result(timeout=20)
        self.assertEqual([row.license_id for row in self.rows() if row.active], [newer.license_id])
        with self.assertRaises(LicenseError):
            self.write(old)
