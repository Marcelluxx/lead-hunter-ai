import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from src.application.budgets import BudgetService
from src.application.jobs import JobService
from src.application.secrets import CredentialService
from src.application.workspaces import bootstrap_platform
from src.domain.feature_licenses import LicenseScope, SubjectKind
from src.infrastructure.models import UserModel, WorkspaceMembershipModel
from src.licensing.settings import LicenseSettings
from src.web.app import create_app
from src.web.dependencies import WebRuntime
from tests.license_helpers import FakeClock, license_claims, local_scope, signed_test_license, test_key_pair
from tests.platform_helpers import platform_fixture
from tests.test_api_security import Publisher


class FeatureLicenseApiTests(unittest.TestCase):
    def setUp(self):
        self.database, passwords, cipher, authentication = platform_fixture()
        self.addCleanup(self.database.engine.dispose)
        with self.database.session() as session:
            self.admin, workspace = bootstrap_platform(session, email='admin@example.test',
                password='correct horse battery staple', display_name='Admin', workspace_slug='license-test',
                workspace_name='License', hard_limit='10', passwords=passwords)
            self.viewer = UserModel(email='viewer@example.test', password_hash=passwords.hash('viewer secure password'),
                                    display_name='Viewer')
            session.add(self.viewer)
            session.flush()
            session.add(WorkspaceMembershipModel(user_id=self.viewer.id, workspace_id=workspace.id, role='viewer'))
            self.workspace_id = workspace.id
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.private, public = test_key_pair()
        trust = Path(tmp.name) / 'trust.json'
        trust.write_text(json.dumps({'version': 1, 'issuer': 'test-owner', 'keys': {'test-key': public.decode()}}))
        self.installation = uuid4()
        self.scope = LicenseScope(self.installation, SubjectKind.WORKSPACE_USER, self.admin.id, self.workspace_id)
        self.settings = LicenseSettings('test-owner', trust, Path(tmp.name), self.installation)
        self.clock = FakeClock(10)
        timer = patch('src.application.license_clock.SystemClock.now_epoch', side_effect=self.clock.now_epoch)
        timer.start()
        self.addCleanup(timer.stop)
        budgets = BudgetService()
        self.runtime = WebRuntime(database=self.database, authentication=authentication,
            jobs=JobService(budgets=budgets, publisher=Publisher()), budgets=budgets,
            credentials=CredentialService(cipher), license_settings=self.settings)
        self.client = TestClient(create_app(self.runtime), base_url='https://testserver')
        self.features_url = f'/workspaces/{self.workspace_id}/features'
        self.url = f'/workspaces/{self.workspace_id}/feature-licenses/{self.admin.id}'
        self.token = signed_test_license(license_claims(scope=self.scope), self.private)

    def login(self, mfa=False, viewer=False):
        response = self.client.post('/auth/login', json={'email': 'viewer@example.test' if viewer else 'admin@example.test',
            'password': 'viewer secure password' if viewer else 'correct horse battery staple'})
        token = response.json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        if mfa:
            enrollment = self.client.post('/auth/mfa/enrollment', headers=headers).json()
            elevated = self.client.post('/auth/mfa/confirm', headers=headers,
                json={'code': enrollment['recovery_codes'][0]}).json()['access_token']
            headers = {'Authorization': f'Bearer {elevated}'}
        return headers

    def test_license_import_requires_authenticated_admin_mfa(self):
        self.assertEqual(self.client.get(self.features_url).status_code, 401)
        self.assertEqual(self.client.put(self.url, json={'token': self.token}, headers=self.login()).status_code, 403)
        self.assertEqual(self.client.put(self.url, json={'token': self.token}, headers=self.login(viewer=True)).status_code, 403)
        headers = self.login(mfa=True)
        self.assertEqual(self.client.put(self.url, json={'token': self.token}, headers=headers).status_code, 200)
        self.assertEqual(self.client.put(self.url, json={'token': self.token, 'features': ['*']}, headers=headers).status_code, 422)
        self.assertEqual(self.client.get(f'/workspaces/{uuid4()}/features', headers=headers).status_code, 403)

    def test_signed_target_cannot_be_reassigned(self):
        headers = self.login(mfa=True)
        other_url = f'/workspaces/{self.workspace_id}/feature-licenses/{self.viewer.id}'
        self.assertEqual(self.client.put(other_url, json={'token': self.token}, headers=headers).status_code, 422)
        local = signed_test_license(license_claims(scope=local_scope()), self.private)
        self.assertEqual(self.client.put(self.url, json={'token': local}, headers=headers).status_code, 422)
        self.assertEqual(self.client.put(self.url, json={'token': 'forged'}, headers=headers).status_code, 422)

    def test_self_status_survives_expiry(self):
        headers = self.login(mfa=True)
        self.assertEqual(self.client.put(self.url, json={'token': self.token}, headers=headers).status_code, 200)
        self.clock.set(100)
        response = self.client.get(self.url, headers=self.login())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['license_status'], 'expired')
        self.assertEqual(response.json()['expires_at'], '1970-01-01T00:01:40Z')

    def test_unconfigured_license_runtime_keeps_base_available(self):
        client = TestClient(create_app(replace(self.runtime, license_settings=None)))
        headers = self.login()
        self.assertEqual(client.get('/health/live').status_code, 200)
        response = client.get(self.features_url, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 3)
        self.assertTrue(all(x['license_status'] == 'missing' and not x['granted'] for x in response.json()))
        self.assertEqual(client.get(self.url, headers=headers).status_code, 503)

    def test_api_never_echoes_signed_token(self):
        headers = self.login(mfa=True)
        for response in (self.client.put(self.url, json={'token': self.token}, headers=headers),
                         self.client.get(self.url, headers=headers), self.client.get(self.features_url, headers=headers)):
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn(self.token, response.text)
        response = self.client.delete(self.url + '/' + str(license_claims().license_id), headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['license_status'], 'revoked')
        oversized = self.token + ('x' * 16384)
        response = self.client.put(self.url, json={'token': oversized}, headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(self.token, response.text)
