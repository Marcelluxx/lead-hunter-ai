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
