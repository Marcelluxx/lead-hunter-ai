import unittest

from fastapi.testclient import TestClient

from src.application.budgets import BudgetService
from src.application.jobs import JobService
from src.application.secrets import CredentialService
from src.application.workspaces import bootstrap_platform
from src.web.app import create_app
from src.web.dependencies import WebRuntime
from tests.platform_helpers import platform_fixture


class Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, job_id):
        self.messages.append(job_id)


class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.database, self.passwords, cipher, authentication = platform_fixture()
        with self.database.session() as session:
            user, workspace = bootstrap_platform(
                session,
                email="admin@example.test",
                password="correct horse battery staple",
                display_name="Admin",
                workspace_slug="first-workspace",
                workspace_name="First",
                hard_limit="10",
                passwords=self.passwords,
            )
            self.workspace_id = workspace.id
        self.publisher = Publisher()
        budgets = BudgetService()
        runtime = WebRuntime(
            database=self.database,
            authentication=authentication,
            jobs=JobService(budgets=budgets, publisher=self.publisher),
            budgets=budgets,
            credentials=CredentialService(cipher),
        )
        self.client = TestClient(create_app(runtime), base_url="https://testserver")

    def tearDown(self):
        self.database.engine.dispose()

    def _login(self):
        response = self.client.post(
            "/auth/login",
            json={
                "email": "admin@example.test",
                "password": "correct horse battery staple",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def test_product_routes_reject_anonymous_and_job_message_is_uuid_only(self):
        url = f"/workspaces/{self.workspace_id}/jobs"
        self.assertEqual(
            self.client.post(
                url,
                headers={"Idempotency-Key": "anonymous"},
                json={"kind": "audit", "parameters": {}, "estimated_cost": "1"},
            ).status_code,
            401,
        )
        token = self._login()
        response = self.client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "authorized",
            },
            json={"kind": "audit", "parameters": {"query": "dentisti"}, "estimated_cost": "1"},
        )
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(str(self.publisher.messages[0]), response.json()["id"])

    def test_secret_management_requires_admin_mfa_and_never_echoes_value(self):
        token = self._login()
        url = f"/workspaces/{self.workspace_id}/secrets/google"
        response = self.client.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "must-not-be-returned"},
        )
        self.assertEqual(response.status_code, 403)
        enrollment = self.client.post(
            "/auth/mfa/enrollment", headers={"Authorization": f"Bearer {token}"}
        )
        code = enrollment.json()["recovery_codes"][0]
        elevated = self.client.post(
            "/auth/mfa/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": code},
        ).json()["access_token"]
        response = self.client.put(
            url,
            headers={"Authorization": f"Bearer {elevated}"},
            json={"value": "must-not-be-returned"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("must-not-be-returned", response.text)


if __name__ == "__main__":
    unittest.main()
