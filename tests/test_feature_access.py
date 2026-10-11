import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.application.feature_access import FeatureAccessService
from src.application.feature_licenses import LicenseService
from src.domain.feature_licenses import FeatureAction, FeatureContext, LicenseError, LicenseScope, SubjectKind
from src.domain.identity import Permission
from src.infrastructure.license_local_store import LocalLicenseStore
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import LicenseVerifier
from tests.license_helpers import FakeClock, license_claims, signed_test_license, test_key_pair


class AvailableCatalog(FeatureCatalog):
    def all(self):
        return tuple(replace(item, module_status='available') for item in super().all())


class PlannedDiagnosticCatalog(FeatureCatalog):
    def all(self):
        return tuple(replace(item, module_status='planned') if item.feature_id == 'diagnostics.full' else item
                     for item in super().all())


class FeatureAccessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = LocalLicenseStore(Path(tmp.name))
        identity = store.installation_id()
        self.scope = LicenseScope(identity, SubjectKind.INSTALLATION, identity)
        self.private, public = test_key_pair()
        self.clock = FakeClock(10)
        self.licenses = LicenseService(store, LicenseVerifier(TrustedLicenseKeys(
            'test-owner', {'test-key': public}), FeatureCatalog()), self.clock)
        self.context = FeatureContext(self.scope, frozenset(Permission), True, True)
        self.access = FeatureAccessService(self.licenses, AvailableCatalog())
        self.claims = license_claims(scope=self.scope)

    def activate(self):
        self.licenses.import_license(self.scope, signed_test_license(self.claims, self.private))

    def test_expiry_blocks_next_step_and_sensitive_delivery(self):
        self.activate()
        self.assertEqual(self.access.require(self.context, 'diagnostics.full').license_id, self.claims.license_id)
        def protected_call():
            self.access.require(self.context, 'diagnostics.full')
            result = 'reserved-result'
            self.clock.set(100)
            self.access.require(self.context, 'diagnostics.full', action=FeatureAction.VIEW)
            return result
        with self.assertRaises(LicenseError) as caught:
            protected_call()
        self.assertEqual(caught.exception.code, 'license_expired')
        self.assertEqual(self.licenses.summary(self.scope).license_status, 'expired')
        # Public status remains readable and cannot trigger a protected execution.
        self.assertFalse(any(item.granted for item in self.access.list_status(self.context)))

    def test_roles_and_mfa_never_replace_license(self):
        with self.assertRaises(LicenseError) as caught:
            self.access.require(self.context, 'diagnostics.full')
        self.assertEqual(caught.exception.code, 'license_missing')
        self.activate()
        for context in (replace(self.context, principal_active=False),):
            with self.assertRaises(LicenseError):
                self.access.require(context, 'diagnostics.full')
        # Role/MFA restrictions apply to authenticated server scopes.
        from tests.license_helpers import managed_scope
        managed = replace(self.context, scope=managed_scope(), mfa_verified=False)
        with self.assertRaises(LicenseError):
            self.access.require(managed, 'diagnostics.full')

    def test_planned_feature_is_not_executable(self):
        self.activate()
        access = FeatureAccessService(self.licenses, PlannedDiagnosticCatalog())
        with self.assertRaises(LicenseError) as caught:
            access.require(self.context, 'diagnostics.full')
        self.assertEqual(caught.exception.code, 'feature_unavailable')
        diag = next(x for x in access.list_status(self.context) if x.feature_id == 'diagnostics.full')
        self.assertTrue(diag.granted)
        self.assertEqual(diag.module_status, 'planned')
