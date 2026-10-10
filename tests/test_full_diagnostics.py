import json
import pickle
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile
from uuid import uuid4

from src.application.diagnostics import DiagnosticSession, DiagnosticError, purge_diagnostic_archives
from src.domain.feature_licenses import LicenseError, SubjectKind, FeatureContext
from src.domain.identity import Permission
from src.licensing.catalog import FeatureCatalog
from tests.reference_export_helpers import ReferenceExportFixture
from tests.license_helpers import seed_license_subject, license_claims, signed_test_license, FakeClock


class DiagnosticCatalog(FeatureCatalog):
    def all(self):
        return tuple(replace(x, module_status='available') if x.feature_id == 'diagnostics.full' else x
                     for x in super().all())


def diagnostic_fixture(testcase, *, activate=True, available=True):
    if available:
        override = patch('src.licensing.catalog.FeatureCatalog', DiagnosticCatalog)
        override.start(); testcase.addCleanup(override.stop)
    fx = ReferenceExportFixture(testcase, available=False)
    fx.claims = replace(fx.claims, features=('diagnostics.full',))
    fx.context = FeatureContext(fx.scope, frozenset(Permission), False, True)
    if activate:
        fx.activate()
    return fx


class FullDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.fx = diagnostic_fixture(self)

    def session(self, **kwargs):
        return DiagnosticSession(self.fx.access, lambda: self.fx.context, **kwargs)

    def test_real_signed_archive_redacts_nested_secrets_and_expires(self):
        run = self.session(secrets=('configured-secret-sentinel',))
        run.capture('page', {'content': '<html>configured-secret-sentinel mario@example.com</html>',
                            'source': 'https://x.test/?token=unsafe', 'data': {'password': 'nested-secret'}})
        run.capture('llm_request', {'content': 'proprietary prompt'})
        with ZipFile(BytesIO(run.export_bytes())) as archive:
            combined = b''.join(archive.read(x) for x in archive.namelist())
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['schema_version'], 1)
            self.assertEqual(manifest['record_count'], 2)
            self.assertLessEqual(manifest['expires_at'], self.fx.claims.expires_at)
        for value in [b'configured-secret-sentinel', b'mario@example.com', b'unsafe', b'nested-secret']:
            self.assertNotIn(value, combined)
        self.assertIn(b'proprietary prompt', combined)
        with self.assertRaisesRegex(TypeError, 'runtime_diagnostics_not_serializable'):
            pickle.dumps(run)

    def test_common_credential_formats_are_redacted_in_reopened_archive(self):
        samples = [
            '{"authorization": "Basic QUJDREVGRw==", "cookie": "session=COOKIE_SENTINEL"}',
            '<input type="hidden" name="csrf_token" value="HTML_SENTINEL"><meta name="api-key" content="META_SENTINEL"><h1>Useful heading</h1>',
            json.dumps({'page': '{"token": "ESCAPED_SENTINEL"}'}),
            'https://site.test/?api%5Fkey=URL_SENTINEL',
        ]
        run = self.session()
        for content in samples:
            run.capture('page', {'content': content})
        with ZipFile(BytesIO(run.export_bytes())) as archive:
            raw = b''.join(archive.read(name) for name in archive.namelist())
            events = [json.loads(archive.read(name)) for name in archive.namelist() if name.startswith('event-')]
        for secret in [b'QUJDREVGRw==', b'COOKIE_SENTINEL', b'HTML_SENTINEL', b'META_SENTINEL', b'ESCAPED_SENTINEL', b'URL_SENTINEL']:
            self.assertNotIn(secret, raw)
        self.assertIn(b'Useful heading', raw)
        self.assertIsInstance(json.loads(events[2]['payload']['content']), dict)

    def test_denied_license_never_collects_or_exports(self):
        run = self.session()
        self.fx.licenses.revoke_license(self.fx.scope, self.fx.claims.license_id)
        for operation in [lambda: run.capture('page', {'content': 'secret'}), run.export_bytes]:
            with self.assertRaisesRegex(LicenseError, '^license_revoked$'):
                operation()
        missing = diagnostic_fixture(self, activate=False)
        with self.assertRaisesRegex(LicenseError, '^license_missing$'):
            DiagnosticSession(missing.access, lambda: missing.context)

    def test_validation_provider_boundary_and_limits(self):
        for hours in [True, 0, 169, 1.5]:
            with self.assertRaisesRegex(DiagnosticError, '^diagnostic_invalid$'):
                self.session(retention_hours=hours)
        run = self.session()
        for payload in [{'data': {'places': []}}, {'rating': 4.9}, {'content': object()}]:
            with self.assertRaisesRegex(DiagnosticError, '^diagnostic_invalid$'):
                run.capture('page', payload)
        with self.assertRaisesRegex(DiagnosticError, '^diagnostic_limit_exceeded$'):
            run.capture('page', {'content': 'x' * (1024 * 1024)})
        for index in range(256):
            run.capture('page', {'content': str(index)})
        with self.assertRaisesRegex(DiagnosticError, '^diagnostic_limit_exceeded$'):
            run.capture('page', {'content': 'extra'})

    def test_parallel_records_and_session_isolation(self):
        run, other = self.session(), self.session()
        with ThreadPoolExecutor(max_workers=6) as executor:
            list(executor.map(lambda i: run.capture('page', {'content': str(i)}), range(80)))
        with ZipFile(BytesIO(run.export_bytes())) as archive:
            contents = [json.loads(archive.read(name))['payload']['content']
                        for name in archive.namelist() if name != 'manifest.json']
        self.assertEqual(set(contents), {str(i) for i in range(80)})
        with ZipFile(BytesIO(other.export_bytes())) as archive:
            self.assertEqual(json.loads(archive.read('manifest.json'))['record_count'], 0)

    def test_aggregate_budget_is_enforced_with_concurrent_large_records(self):
        run = self.session()
        def capture(_):
            try:
                run.capture('page', {'content': 'x' * 900000})
                return True
            except DiagnosticError as exc:
                self.assertEqual(exc.code, 'diagnostic_limit_exceeded')
                return False
        with ThreadPoolExecutor(max_workers=4) as pool:
            successes = list(pool.map(capture, range(12)))
        self.assertTrue(any(successes)); self.assertFalse(all(successes))
        with ZipFile(BytesIO(run.export_bytes())) as archive:
            self.assertLessEqual(sum(len(archive.read(x)) for x in archive.namelist() if x != 'manifest.json'), 8 * 1024 * 1024)

    def test_sealed_session_and_retention_deadline_are_enforced(self):
        self.fx.activate(replace(self.fx.claims, license_id=uuid4(), expires_at=10000))
        run = self.session(retention_hours=1)
        run.seal()
        with self.assertRaisesRegex(DiagnosticError, '^diagnostic_closed$'):
            run.capture('summary', {'content': 'later'})
        run.export_bytes()
        self.fx.clock.set(3610)
        with self.assertRaisesRegex(DiagnosticError, '^diagnostic_expired$'): run.export_bytes()
        with self.assertRaisesRegex(DiagnosticError, '^diagnostic_expired$'): run.require_execute()

    def test_purge_removes_only_owned_expired_uuid_archives(self):
        root = self.fx.root / 'private'; root.mkdir()
        expired, fresh, custom = root / f'{uuid4()}.zip', root / f'{uuid4()}.zip', root / 'customer.zip'
        for path, expires in [(expired, 10), (fresh, 100), (custom, 10)]:
            with ZipFile(path, 'w') as archive:
                archive.writestr('manifest.json', json.dumps({'schema_version': 1,
                    'run_id': path.stem, 'expires_at': expires, 'classification': 'PRIVATE_REDACTED_DIAGNOSTICS'}))
        unrelated = root / 'keep.txt'; unrelated.write_text('keep')
        self.assertEqual(purge_diagnostic_archives(root, now=20), 1)
        self.assertFalse(expired.exists()); self.assertTrue(fresh.exists())
        self.assertTrue(custom.exists()); self.assertTrue(unrelated.exists())

    def test_revocation_during_serialization_or_fsync_preserves_previous_file(self):
        destination = self.fx.root / 'existing.zip'; destination.write_bytes(b'previous')
        for stage in ['zip', 'fsync']:
            with self.subTest(stage=stage):
                fx = diagnostic_fixture(self)
                run = DiagnosticSession(fx.access, lambda: fx.context)
                run.capture('summary', {'content': 'okay'})
                original = ZipFile.writestr
                def write(archive, *args, **kwargs):
                    result = original(archive, *args, **kwargs)
                    fx.licenses.revoke_license(fx.scope, fx.claims.license_id)
                    return result
                def revoke(_): fx.licenses.revoke_license(fx.scope, fx.claims.license_id)
                target = patch('zipfile.ZipFile.writestr', new=write) if stage == 'zip' else patch('os.fsync', side_effect=revoke)
                with target, self.assertRaises(LicenseError):
                    run.save(destination)
                self.assertEqual(destination.read_bytes(), b'previous')
                self.assertEqual(list(self.fx.root.glob('.diagnostic-*')), [])

    def test_server_mfa_and_current_permissions_required(self):
        from uuid import uuid4
        from src.application.authentication import AuthContext
        from src.application.feature_access import FeatureAccessService, server_feature_context
        from src.application.feature_licenses import LicenseService
        from src.infrastructure.license_repository import SqlLicenseRepository
        from src.infrastructure.models import WorkspaceMembershipModel
        from tests.platform_helpers import platform_fixture
        database, *_ = platform_fixture(); self.addCleanup(database.engine.dispose)
        scope = seed_license_subject(database)
        claims = license_claims(scope=scope)
        auth = AuthContext(scope.subject_id, uuid4(), True)
        with database.session(scope.workspace_id) as db:
            licenses = LicenseService(SqlLicenseRepository(db, scope.installation_id), self.fx.licenses.verifier, FakeClock(10))
            licenses.import_license(scope, signed_test_license(claims, self.fx.private))
            access = FeatureAccessService(licenses, DiagnosticCatalog())
            run = DiagnosticSession(access, lambda: server_feature_context(db, auth=auth,
                workspace_id=scope.workspace_id, installation_id=scope.installation_id))
            auth = replace(auth, mfa_verified=False)
            with self.assertRaisesRegex(LicenseError, '^feature_role_denied$'): run.require_execute()
            with self.assertRaisesRegex(LicenseError, '^feature_role_denied$'): run.require_view()
            auth = replace(auth, mfa_verified=True)
            member = db.query(WorkspaceMembershipModel).filter_by(user_id=scope.subject_id).one()
            member.role = 'viewer'; db.flush()
            with self.assertRaisesRegex(LicenseError, '^feature_role_denied$'): run.require_execute()
            run.export_bytes()  # Viewer has VIEW_AUDIT_LOG; it does not imply START_JOB.
            member.role = 'operator'; db.flush()
            run.require_execute()
            with self.assertRaisesRegex(LicenseError, '^feature_role_denied$'): run.export_bytes()
