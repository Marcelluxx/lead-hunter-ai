import unittest
import uuid

from src.application.authentication import AuthenticationError
from src.application.workspaces import bootstrap_platform
from src.infrastructure.models import SessionModel
from tests.platform_helpers import platform_fixture


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.database, self.passwords, self.cipher, self.auth = platform_fixture()
        with self.database.session() as session:
            self.user, self.workspace = bootstrap_platform(
                session,
                email="Admin@Example.Test",
                password="correct horse battery staple",
                display_name="Admin",
                workspace_slug="first-workspace",
                workspace_name="First",
                hard_limit="10",
                passwords=self.passwords,
            )
            self.user_id = self.user.id

    def tearDown(self):
        self.database.engine.dispose()

    def test_login_is_uniform_and_access_session_is_revocable(self):
        with self.database.session() as session:
            with self.assertRaisesRegex(AuthenticationError, "Credenziali non valide"):
                self.auth.login(session, email="missing@example.test", password="wrong")
        with self.database.session() as session:
            tokens = self.auth.login(
                session,
                email="ADMIN@example.test",
                password="correct horse battery staple",
            )
            context = self.auth.authenticate_access_token(session, tokens.access_token)
            self.assertEqual(context.user_id, self.user_id)
            self.auth.logout(session, context=context)
        with self.database.session() as session:
            with self.assertRaisesRegex(AuthenticationError, "Sessione non valida"):
                self.auth.authenticate_access_token(session, tokens.access_token)

    def test_refresh_rotates_token_and_reuse_revokes_session(self):
        with self.database.session() as session:
            tokens = self.auth.login(
                session,
                email="admin@example.test",
                password="correct horse battery staple",
            )
            context = self.auth.authenticate_access_token(session, tokens.access_token)
            rotated = self.auth.refresh(
                session,
                session_id=context.session_id,
                refresh_token=tokens.refresh_token,
                csrf_token=tokens.csrf_token,
            )
            self.assertNotEqual(tokens.refresh_token, rotated.refresh_token)
        with self.assertRaises(AuthenticationError):
            with self.database.session() as session:
                self.auth.refresh(
                    session,
                    session_id=context.session_id,
                    refresh_token=tokens.refresh_token,
                    csrf_token=tokens.csrf_token,
                )
        with self.database.session() as session:
            record = session.get(SessionModel, context.session_id)
            self.assertIsNotNone(record.revoked_at)

    def test_admin_mfa_enrollment_returns_recovery_codes_once(self):
        with self.database.session() as session:
            tokens = self.auth.login(
                session,
                email="admin@example.test",
                password="correct horse battery staple",
            )
            context = self.auth.authenticate_access_token(session, tokens.access_token)
            enrollment = self.auth.begin_mfa_enrollment(session, context=context)
            elevated = self.auth.confirm_mfa(
                session, context=context, code=enrollment.recovery_codes[0]
            )
            elevated_context = self.auth.authenticate_access_token(session, elevated.access_token)
            self.assertTrue(elevated_context.mfa_verified)
            self.assertNotIn(enrollment.recovery_codes[0], str(session.get(SessionModel, context.session_id)))
        with self.database.session() as session:
            with self.assertRaises(AuthenticationError):
                self.auth.verify_mfa(session, context=context, code=enrollment.recovery_codes[0])

    def test_oidc_mapping_never_creates_or_derives_a_role(self):
        with self.database.session() as session:
            identity = self.auth.map_oidc_identity(
                session,
                provider="enterprise",
                subject="immutable-provider-subject",
                user_id=self.user_id,
            )
            self.assertEqual(identity.user_id, self.user_id)
            self.assertFalse(hasattr(identity, "role"))


if __name__ == "__main__":
    unittest.main()
