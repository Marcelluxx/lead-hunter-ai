import unittest
import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from src.infrastructure.database import Database
from src.infrastructure.models import (
    Base,
    UsageBudgetModel,
    UserModel,
    WorkspaceMembershipModel,
    WorkspaceModel,
)


class PlatformSchemaTests(unittest.TestCase):
    def setUp(self):
        self.database = Database("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.database.engine)

    def tearDown(self):
        self.database.engine.dispose()

    def test_schema_contains_control_boundary_tables(self):
        expected = {
            "users",
            "sessions",
            "mfa_credentials",
            "oidc_identities",
            "workspaces",
            "workspace_memberships",
            "provider_credentials",
            "jobs",
            "job_attempts",
            "usage_budgets",
            "usage_reservations",
            "usage_ledger",
            "audit_events",
        }
        self.assertEqual(set(Base.metadata.tables), expected)

    def test_membership_role_and_workspace_user_pair_are_constrained(self):
        with self.database.session() as session:
            user = UserModel(
                email="admin@example.test",
                password_hash="hash",
                display_name="Admin",
            )
            workspace = WorkspaceModel(slug="acme", name="Acme")
            session.add_all([user, workspace])
            session.flush()
            session.add(
                WorkspaceMembershipModel(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    role="admin",
                )
            )

        with self.assertRaises(IntegrityError):
            with self.database.session() as session:
                user = session.query(UserModel).one()
                workspace = session.query(WorkspaceModel).one()
                session.add(
                    WorkspaceMembershipModel(
                        workspace_id=workspace.id,
                        user_id=user.id,
                        role="owner",
                    )
                )

    def test_budget_rejects_negative_limits(self):
        with self.assertRaises(IntegrityError):
            with self.database.session() as session:
                workspace = WorkspaceModel(slug="negative", name="Negative")
                session.add(workspace)
                session.flush()
                session.add(
                    UsageBudgetModel(
                        workspace_id=workspace.id,
                        hard_limit=Decimal("-1"),
                    )
                )


if __name__ == "__main__":
    unittest.main()
