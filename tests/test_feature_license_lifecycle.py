import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from src.application.authentication import AuthContext
from src.application.feature_access import FeatureAccessService, server_feature_context
from src.application.feature_licenses import LicenseService
from src.application.license_clock import GuardedClock
from src.application.managed_licenses import ManagedLicenseService
from src.domain.feature_licenses import FeatureContext, LicenseError, LicenseScope, SubjectKind
from src.domain.identity import Permission
from src.infrastructure.license_local_store import LocalLicenseStore
from src.infrastructure.license_repository import SqlLicenseRepository
from src.infrastructure.models import AuditEventModel
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import LicenseVerifier
from tests.license_helpers import FakeClock, license_claims, seed_license_subject
from tests.platform_helpers import platform_fixture
from tests.test_feature_access import AvailableCatalog
from tools.license_issuer.keys import generate_issuer_keys
from tools.license_issuer.issuance import issue_license


class FeatureLicenseLifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.private, self.public = self.root / 'private.pem', self.root / 'public.pem'
        generate_issuer_keys(private_path=self.private, public_path=self.public, passphrase=b'test-only')
        self.verifier = LicenseVerifier(TrustedLicenseKeys('test-owner', {'test-key': self.public.read_bytes()}),
                                       FeatureCatalog())
        self.clock = FakeClock(10)

    def issue(self, claims):
        path = self.root / (str(claims.license_id) + '.lh')
        issue_license(claims, private_path=self.private, passphrase=b'test-only',
                      kid='test-key', output_path=path)
        return path.read_text()

    def test_local_offline_expiry_renewal_and_revocation(self):
        store = LocalLicenseStore(self.root / 'state')
        identity = store.installation_id()
        scope = LicenseScope(identity, SubjectKind.INSTALLATION, identity)
        service = LicenseService(store, self.verifier, GuardedClock(self.clock, store))
        access = FeatureAccessService(service, AvailableCatalog())
        context = FeatureContext(scope, frozenset(Permission), False, True)
        claims = license_claims(scope=scope)
        service.import_license(scope, self.issue(claims))
        self.assertEqual(access.require(context, 'diagnostics.full').license_id, claims.license_id)
        self.clock.set(100)
        with self.assertRaises(LicenseError):
            access.require(context, 'diagnostics.full')
        self.assertEqual(service.summary(scope).license_status, 'expired')
        renewal = replace(claims, license_id=uuid4(), expires_at=200)
        service.import_license(scope, self.issue(renewal))
        self.assertEqual(access.require(context, 'diagnostics.full').expires_at, 200)
        service.revoke_license(scope, renewal.license_id)
        with self.assertRaises(LicenseError):
            access.require(context, 'diagnostics.full')
        self.assertEqual(service.summary(scope).license_status, 'revoked')

    def test_managed_grant_lifecycle_is_scoped_and_redacted(self):
        database, *_ = platform_fixture()
        self.addCleanup(database.engine.dispose)
        scope = seed_license_subject(database)
        other = seed_license_subject(database)
        claims = license_claims(scope=scope)
        token = self.issue(claims)
        actor = AuthContext(scope.subject_id, uuid4(), True)
        with database.session(scope.workspace_id) as session:
            licenses = LicenseService(SqlLicenseRepository(session, scope.installation_id), self.verifier, self.clock)
            managed = ManagedLicenseService(licenses)
            args = dict(actor=actor, workspace_id=scope.workspace_id,
                        user_id=scope.subject_id, installation_id=scope.installation_id)
            summary = managed.import_for_user(session, **args, token=token)
            self.assertNotIn(token, repr(summary))
            with self.assertRaises(LicenseError):
                licenses.import_license(other, token)
            self.clock.set(100)
            self.assertEqual(managed.status_for_user(session, **args).license_status, 'expired')
            renewal = replace(claims, license_id=uuid4(), expires_at=200, features=('export.no_website',))
            managed.import_for_user(session, **args, token=self.issue(renewal))
            context = server_feature_context(session, auth=actor, workspace_id=scope.workspace_id,
                                            installation_id=scope.installation_id)
            self.assertEqual(FeatureAccessService(licenses, AvailableCatalog()).require(
                context, 'export.no_website').features, ('export.no_website',))
            managed.revoke_for_user(session, **args, license_id=renewal.license_id)
            session.flush()
            events = session.scalars(select(AuditEventModel)).all()
            self.assertEqual([e.action for e in events], ['license.imported', 'license.renewed', 'license.revoked'])
            self.assertNotIn(token, repr([e.details for e in events]))
