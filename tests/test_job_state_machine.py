import unittest

from src.application.budgets import BudgetService
from src.application.jobs import JobService
from src.application.workspaces import bootstrap_platform
from src.domain.jobs import InvalidJobTransition, JobState
from src.domain.discovery import ProviderPayloadError
from src.infrastructure.models import JobModel
from tests.platform_helpers import platform_fixture


class RecordingPublisher:
    def __init__(self):
        self.messages = []

    def publish(self, job_id):
        self.messages.append(job_id)


class JobServiceTests(unittest.TestCase):
    def setUp(self):
        self.database, self.passwords, _, _ = platform_fixture()
        self.publisher = RecordingPublisher()
        self.service = JobService(budgets=BudgetService(), publisher=self.publisher)
        with self.database.session() as session:
            self.user, self.workspace = bootstrap_platform(
                session,
                email="admin@example.test",
                password="correct horse battery staple",
                display_name="Admin",
                workspace_slug="first-workspace",
                workspace_name="First",
                hard_limit="10",
                passwords=self.passwords,
            )

    def tearDown(self):
        self.database.engine.dispose()

    def test_idempotency_publishes_only_uuid_once(self):
        with self.database.session() as session:
            first = self.service.create(
                session,
                workspace_id=self.workspace.id,
                user_id=self.user.id,
                kind="audit",
                parameters={"query": "dentisti"},
                estimated_cost="2",
                idempotency_key="request-1",
            )
        with self.database.session() as session:
            second = self.service.create(
                session,
                workspace_id=self.workspace.id,
                user_id=self.user.id,
                kind="audit",
                parameters={"query": "ignored"},
                estimated_cost="2",
                idempotency_key="request-1",
            )
            self.assertFalse(second.created)
            self.assertEqual(first.job.id, second.job.id)
        self.assertEqual(self.publisher.messages, [first.job.id])

    def test_invalid_transition_is_rejected(self):
        with self.database.session() as session:
            created = self.service.create(
                session,
                workspace_id=self.workspace.id,
                user_id=self.user.id,
                kind="audit",
                parameters={},
                estimated_cost="1",
                idempotency_key="transition",
            )
            with self.assertRaises(InvalidJobTransition):
                self.service.transition(
                    session, job_id=created.job.id, target=JobState.COMPLETED
                )

    def test_provider_payload_cannot_enter_persistent_job_parameters(self):
        with self.assertRaises(ProviderPayloadError):
            with self.database.session() as session:
                self.service.create(
                    session,
                    workspace_id=self.workspace.id,
                    user_id=self.user.id,
                    kind="audit",
                    parameters={"places": [{"displayName": {"text": "Forbidden"}}]},
                    estimated_cost="1",
                    idempotency_key="provider-payload",
                )


if __name__ == "__main__":
    unittest.main()
