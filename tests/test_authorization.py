import unittest

from src.application.authentication import AuthContext
from src.application.authorization import AuthorizationDenied, require_permission
from src.application.workspaces import bootstrap_platform
from src.domain.identity import Permission
from src.infrastructure.models import UserModel, WorkspaceMembershipModel, WorkspaceModel
from tests.platform_helpers import platform_fixture


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.database, self.passwords, _, _ = platform_fixture()
        with self.database.session() as session:
            self.admin, self.workspace = bootstrap_platform(
                session,
                email="admin@example.test",
                password="correct horse battery staple",
                display_name="Admin",
                workspace_slug="first-workspace",
                workspace_name="First",
                hard_limit="10",
                passwords=self.passwords,
            )
            self.viewer = UserModel(
                email="viewer@example.test",
                password_hash=self.passwords.hash("another secure password"),
                display_name="Viewer",
            )
            self.other = WorkspaceModel(slug="other-workspace", name="Other")
            session.add_all([self.viewer, self.other])
            session.flush()
            session.add(
                WorkspaceMembershipModel(
                    workspace_id=self.workspace.id,
                    user_id=self.viewer.id,
                    role="viewer",
                )
            )

    def tearDown(self):
        self.database.engine.dispose()

    def test_viewer_cannot_start_job_or_cross_workspace(self):
        with self.database.session() as session:
            with self.assertRaises(AuthorizationDenied):
                require_permission(
                    session,
                    user_id=self.viewer.id,
                    workspace_id=self.workspace.id,
                    permission=Permission.START_JOB,
                    mfa_verified=False,
                )
            with self.assertRaises(AuthorizationDenied):
                require_permission(
                    session,
                    user_id=self.viewer.id,
                    workspace_id=self.other.id,
                    permission=Permission.VIEW_RESULTS,
                    mfa_verified=False,
                )

    def test_admin_management_requires_mfa(self):
        with self.database.session() as session:
            with self.assertRaisesRegex(AuthorizationDenied, "MFA"):
                require_permission(
                    session,
                    user_id=self.admin.id,
                    workspace_id=self.workspace.id,
                    permission=Permission.MANAGE_BUDGET,
                    mfa_verified=False,
                )
            role = require_permission(
                session,
                user_id=self.admin.id,
                workspace_id=self.workspace.id,
                permission=Permission.MANAGE_BUDGET,
                mfa_verified=True,
            )
            self.assertEqual(role.value, "admin")


if __name__ == "__main__":
    unittest.main()
