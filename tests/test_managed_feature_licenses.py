import unittest
from dataclasses import replace
from uuid import uuid4

from sqlalchemy import delete, select

from src.application.authentication import AuthContext
from src.application.feature_access import FeatureAccessService, server_feature_context
from src.application.feature_licenses import LicenseService
from src.application.managed_licenses import ManagedLicenseService
from src.domain.feature_licenses import FeatureAction, LicenseError
from src.infrastructure.license_repository import SqlLicenseRepository
from src.infrastructure.models import AuditEventModel, UserModel, WorkspaceMembershipModel
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import LicenseVerifier
from tests.license_helpers import FakeClock, license_claims, seed_license_subject, signed_test_license, test_key_pair
from tests.platform_helpers import platform_fixture
from tests.test_feature_access import AvailableCatalog


class ManagedFeatureLicenseTests(unittest.TestCase):
    def setUp(self):
        self.database, *_ = platform_fixture()
        self.addCleanup(self.database.engine.dispose)
        self.scope = seed_license_subject(self.database)
        self.auth = AuthContext(self.scope.subject_id, uuid4(), True)
        self.private, public = test_key_pair()
        self.verifier = LicenseVerifier(TrustedLicenseKeys('test-owner', {'test-key': public}), FeatureCatalog())
        self.clock = FakeClock(10)
        self.claims = license_claims(scope=self.scope)

    def services(self, session):
        licenses = LicenseService(SqlLicenseRepository(session, self.scope.installation_id), self.verifier, self.clock)
        return ManagedLicenseService(licenses), FeatureAccessService(licenses, AvailableCatalog())

    def arguments(self, actor=None):
        return dict(actor=actor or self.auth, workspace_id=self.scope.workspace_id,
                    user_id=self.scope.subject_id, installation_id=self.scope.installation_id)

    def test_license_audit_is_redacted(self):
        token = signed_test_license(self.claims, self.private)
        with self.database.session(self.scope.workspace_id) as session:
            managed, _ = self.services(session)
            managed.import_for_user(session, **self.arguments(), token=token)
            managed.import_for_user(session, **self.arguments(), token=token)
            managed.revoke_for_user(session, **self.arguments(), license_id=self.claims.license_id)
            session.flush()
            events = session.scalars(select(AuditEventModel)).all()
            self.assertEqual([x.action for x in events], ['license.imported', 'license.revoked'])
            self.assertNotIn(token, str([x.details for x in events]))
            self.assertEqual(events[0].details['features'], 'diagnostics.full')

    def test_inactive_or_removed_member_is_denied(self):
        with self.database.session(self.scope.workspace_id) as session:
            managed, access = self.services(session)
            managed.import_for_user(session, **self.arguments(), token=signed_test_license(self.claims, self.private))
            user = session.get(UserModel, self.scope.subject_id)
            user.is_active = False
            session.flush()
            context = server_feature_context(session, auth=self.auth, workspace_id=self.scope.workspace_id,
                                             installation_id=self.scope.installation_id)
            with self.assertRaises(LicenseError):
                access.require(context, 'diagnostics.full')
            user.is_active = True
            session.execute(delete(WorkspaceMembershipModel).where(WorkspaceMembershipModel.user_id == user.id))
            session.flush()
            context = server_feature_context(session, auth=self.auth, workspace_id=self.scope.workspace_id,
                                             installation_id=self.scope.installation_id)
            with self.assertRaises(LicenseError):
                access.require(context, 'diagnostics.full')

    def test_roles_mfa_and_signed_target_are_enforced_in_service(self):
        with self.database.session(self.scope.workspace_id) as session:
            managed, access = self.services(session)
            token = signed_test_license(self.claims, self.private)
            with self.assertRaises(LicenseError):
                managed.import_for_user(session, **self.arguments(replace(self.auth, mfa_verified=False)), token=token)
            managed.import_for_user(session, **self.arguments(), token=token)
            member = session.scalar(select(WorkspaceMembershipModel))
            member.role = 'viewer'
            session.flush()
            context = server_feature_context(session, auth=replace(self.auth, mfa_verified=False),
                workspace_id=self.scope.workspace_id, installation_id=self.scope.installation_id)
            with self.assertRaises(LicenseError):
                access.require(context, 'diagnostics.full', action=FeatureAction.VIEW)
            with self.assertRaises(LicenseError):
                managed.revoke_for_user(session, **self.arguments(), license_id=self.claims.license_id)
            self.clock.set(100)
            self.assertEqual(managed.status_for_user(session, **self.arguments()).license_status, 'expired')
