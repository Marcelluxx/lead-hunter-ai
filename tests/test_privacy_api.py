import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from src.application.budgets import BudgetService
from src.application.data_subject_requests import DataSubjectRequestService
from src.application.jobs import JobService
from src.application.privacy_policy import WorkspacePrivacyPolicyService
from src.application.secrets import CredentialService
from src.application.suppression import SuppressionService
from src.application.workspaces import bootstrap_platform
from src.web.app import create_app
from src.web.dependencies import WebRuntime
from src.infrastructure.models import UserModel
from tests.platform_helpers import platform_fixture


class _Publisher:
    def publish(self, job_id):
        return None


class PrivacyApiTests(unittest.TestCase):
    def setUp(self):
        self.database, self.passwords, cipher, authentication = platform_fixture()
        with self.database.session() as session:
            _, workspace = bootstrap_platform(
                session,
                email="privacy-admin@example.test",
                password="correct horse battery staple",
                display_name="Privacy Admin",
                workspace_slug="privacy-api",
                workspace_name="Privacy API",
                hard_limit="10",
                passwords=self.passwords,
            )
            self.workspace_id = workspace.id
        budgets = BudgetService()
        suppression = SuppressionService(b"api-privacy-suppression-key-32!!")
        runtime = WebRuntime(
            database=self.database,
            authentication=authentication,
            jobs=JobService(budgets=budgets, publisher=_Publisher()),
            budgets=budgets,
            credentials=CredentialService(cipher),
            privacy_policies=WorkspacePrivacyPolicyService(),
            suppression=suppression,
            data_subject_requests=DataSubjectRequestService(suppression),
        )
        self.client = TestClient(create_app(runtime), base_url="https://testserver")

    def tearDown(self):
        self.database.engine.dispose()

    def _token(self, *, mfa=False):
        token = self.client.post(
            "/auth/login",
            json={
                "email": "privacy-admin@example.test",
                "password": "correct horse battery staple",
            },
        ).json()["access_token"]
        if not mfa:
            return token
        enrollment = self.client.post(
            "/auth/mfa/enrollment", headers={"Authorization": f"Bearer {token}"}
        ).json()
        return self.client.post(
            "/auth/mfa/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": enrollment["recovery_codes"][0]},
        ).json()["access_token"]

    def test_privacy_administration_requires_mfa_and_suppression_never_echoes_identifier(self):
        url = f"/workspaces/{self.workspace_id}/privacy/policy"
        payload = {
            "purpose": "Analisi commerciale B2B",
            "legal_basis": "Legittimo interesse valutato dal titolare",
            "privacy_contact": "privacy@example.it",
            "market": "IT_EU",
            "named_contact_retention_days": 90,
            "policy_version": "privacy-v1",
        }
        self.assertEqual(self.client.put(url, json=payload).status_code, 401)
        token = self._token()
        self.assertEqual(
            self.client.put(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            ).status_code,
            403,
        )
        elevated = self._token(mfa=True)
        response = self.client.put(
            url,
            headers={"Authorization": f"Bearer {elevated}"},
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.text)
        with self.database.session() as session:
            user = session.scalar(
                select(UserModel).where(
                    UserModel.email == "privacy-admin@example.test"
                )
            )
            user.is_platform_admin = False
        global_denied = self.client.post(
            f"/workspaces/{self.workspace_id}/privacy/suppressions",
            headers={"Authorization": f"Bearer {elevated}"},
            json={
                "kind": "email",
                "value": "global-person@example.it",
                "scope": "global",
                "reason": "opposition",
            },
        )
        self.assertEqual(global_denied.status_code, 403, global_denied.text)
        suppression = self.client.post(
            f"/workspaces/{self.workspace_id}/privacy/suppressions",
            headers={"Authorization": f"Bearer {elevated}"},
            json={
                "kind": "email",
                "value": "person@example.it",
                "scope": "workspace",
                "reason": "opposition",
            },
        )
        self.assertEqual(suppression.status_code, 201, suppression.text)
        self.assertNotIn("person@example.it", suppression.text.lower())


if __name__ == "__main__":
    unittest.main()
