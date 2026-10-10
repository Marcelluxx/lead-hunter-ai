import unittest
from dataclasses import replace
from uuid import uuid4

from sqlalchemy import select

from src.application.feature_licenses import LicenseService
from src.infrastructure.license_models import FeatureLicenseGrantModel
from src.infrastructure.license_repository import SqlLicenseRepository, PostgresClockStore
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import LicenseVerifier
from src.domain.feature_licenses import LicenseError
from tests.license_helpers import (FakeClock, license_claims, seed_license_subject,
                                  signed_test_license, test_key_pair)
from tests.platform_helpers import platform_fixture


class FeatureLicenseRepositoryTests(unittest.TestCase):
    def test_clock_commits_with_request_pool_saturated(self):
        import tempfile
        from pathlib import Path
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from sqlalchemy import create_engine, text
        from src.infrastructure.database import Database
        from src.infrastructure.models import Base
        with tempfile.TemporaryDirectory() as root:
            database = Database('sqlite+pysqlite:///' + (Path(root) / 'pool.sqlite').as_posix())
            database.engine.dispose()
            database.engine = create_engine(database.engine.url, pool_size=2, max_overflow=0, pool_timeout=0.2)
            database.session_factory.configure(bind=database.engine)
            Base.metadata.create_all(database.engine)
            barrier = Barrier(2)
            identity = uuid4()
            def request():
                with database.session() as outer:
                    outer.execute(text('SELECT 1'))
                    barrier.wait(timeout=5)
                    return PostgresClockStore(database, identity).advance(1000)
            try:
                with ThreadPoolExecutor(2) as pool:
                    self.assertEqual(list(pool.map(lambda _: request(), range(2))), [1000, 1000])
                self.assertEqual(PostgresClockStore(database, identity).advance(800), 1000)
            finally:
                if hasattr(database, 'close_license_clock_pool'):
                    database.close_license_clock_pool()
                database.engine.dispose()

    def setUp(self):
        self.database, *_ = platform_fixture()
        self.addCleanup(self.database.engine.dispose)
        self.scope = seed_license_subject(self.database)
        self.private, public = test_key_pair()
        self.verifier = LicenseVerifier(TrustedLicenseKeys('test-owner', {'test-key': public}), FeatureCatalog())
        self.claims = license_claims(scope=self.scope)

    def test_grant_lifecycle_is_atomic(self):
        scope = self.scope
        with self.database.session(scope.workspace_id) as session:
            service = LicenseService(SqlLicenseRepository(session, scope.installation_id), self.verifier, FakeClock(10))
            token = signed_test_license(self.claims, self.private)
            service.import_license(scope, token)
            service.import_license(scope, token)
            with self.assertRaises(LicenseError):
                service.import_license(scope, 'invalid')
            newer = replace(self.claims, license_id=uuid4(), features=('export.no_website',))
            service.import_license(scope, signed_test_license(newer, self.private))
            self.assertEqual(service.require_valid(scope).features, ('export.no_website',))
            with self.assertRaises(LicenseError):
                service.import_license(scope, token)
            rows = session.scalars(select(FeatureLicenseGrantModel)).all()
            self.assertEqual(len(rows), 2)
            self.assertEqual(sum(row.active for row in rows), 1)
            # Extracted columns cannot confer privileges absent from the signed token.
            active = next(row for row in rows if row.active)
            active.features = ['diagnostics.full']
            self.assertEqual(service.require_valid(scope).features, ('export.no_website',))
            service.revoke_license(scope, newer.license_id)
            self.assertEqual(service.summary(scope).license_status, 'revoked')
            with self.assertRaises(LicenseError):
                service.import_license(scope, signed_test_license(newer, self.private))

    def test_license_time_only_advances(self):
        clock = PostgresClockStore(self.database, self.scope.installation_id)
        self.assertEqual(clock.advance(1000), 1000)
        self.assertEqual(clock.advance(800), 1000)
        self.assertEqual(clock.advance(1001), 1001)
