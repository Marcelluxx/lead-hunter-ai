import unittest
from uuid import uuid4

from src.domain.feature_licenses import LicenseError
from src.infrastructure.models import JobModel
from src.workers.feature_access import job_feature_context
from tests.license_helpers import seed_license_subject
from tests.platform_helpers import platform_fixture


class WorkerFeatureContextTests(unittest.TestCase):
    def test_job_context_ignores_client_supplied_authorization(self):
        database, *_ = platform_fixture()
        self.addCleanup(database.engine.dispose)
        scope = seed_license_subject(database)
        with database.session(scope.workspace_id) as session:
            job = JobModel(workspace_id=scope.workspace_id, created_by=scope.subject_id,
                kind='test', idempotency_key='test', parameters={'role': 'admin',
                    'mfa_verified': True, 'token': 'forged', 'created_by': str(uuid4())})
            session.add(job)
            session.flush()
            context = job_feature_context(session, job_id=job.id, installation_id=scope.installation_id)
            self.assertEqual(context.scope, scope)
            self.assertFalse(context.mfa_verified)
            with self.assertRaises(LicenseError):
                job_feature_context(session, job_id=uuid4(), installation_id=scope.installation_id)
