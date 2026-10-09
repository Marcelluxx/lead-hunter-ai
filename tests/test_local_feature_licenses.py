import json
import multiprocessing
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from src.application.feature_licenses import LicenseService
from src.application.license_clock import GuardedClock
from src.domain.feature_licenses import LicenseError, LicenseScope, SubjectKind
from src.infrastructure.license_local_store import LocalLicenseStore
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import LicenseVerifier
from tests.license_helpers import FakeClock, license_claims, signed_test_license, test_key_pair


def import_process(root, public, token, ready, start):
    store = LocalLicenseStore(Path(root))
    identity = store.installation_id()
    scope = LicenseScope(identity, SubjectKind.INSTALLATION, identity)
    service = LicenseService(store, LicenseVerifier(TrustedLicenseKeys('test-owner', {'test-key': public}),
                                                    FeatureCatalog()), GuardedClock(FakeClock(10), store))
    ready.put(True)
    start.wait(10)
    service.import_license(scope, token)


class LocalFeatureLicenseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'state'
        self.store = LocalLicenseStore(self.root)
        identity = self.store.installation_id()
        self.scope = LicenseScope(identity, SubjectKind.INSTALLATION, identity)
        self.private, self.public = test_key_pair()
        self.clock = FakeClock(10)
        self.verifier = LicenseVerifier(TrustedLicenseKeys('test-owner', {'test-key': self.public}), FeatureCatalog())
        self.service = LicenseService(self.store, self.verifier, GuardedClock(self.clock, self.store))
        self.claims = license_claims(scope=self.scope)
        self.token = signed_test_license(self.claims, self.private)

    def test_backup_preserves_identity_new_installation_does_not(self):
        self.service.import_license(self.scope, self.token)
        backup = Path(self.tmp.name) / 'backup'
        shutil.copytree(self.root, backup)
        self.assertEqual(LocalLicenseStore(backup).installation_id(), self.scope.installation_id)
        fresh = LocalLicenseStore(Path(self.tmp.name) / 'fresh')
        fresh_id = fresh.installation_id()
        self.assertNotEqual(fresh_id, self.scope.installation_id)
        with self.assertRaises(LicenseError):
            LicenseService(fresh, self.verifier, self.clock).import_license(
                LicenseScope(fresh_id, SubjectKind.INSTALLATION, fresh_id), self.token)

    def test_invalid_renewal_preserves_active_grant(self):
        self.service.import_license(self.scope, self.token)
        for invalid in ('tampered', signed_test_license(replace(self.claims, not_before=20), self.private)):
            with self.assertRaises(LicenseError):
                self.service.import_license(self.scope, invalid)
        self.assertEqual(self.service.require_valid(self.scope).license_id, self.claims.license_id)
        self.clock.set(100)
        summary = self.service.summary(self.scope)
        self.assertEqual((summary.license_status, summary.expires_at), ('expired', 100))

    def test_renewal_replaces_features_and_revoked_jti_cannot_reactivate(self):
        self.service.import_license(self.scope, self.token)
        self.service.import_license(self.scope, self.token)
        new = replace(self.claims, license_id=UUID(int=7), features=('export.no_website',))
        self.service.import_license(self.scope, signed_test_license(new, self.private))
        self.assertEqual(self.service.require_valid(self.scope).features, ('export.no_website',))
        with self.assertRaises(LicenseError) as raised:
            self.service.import_license(self.scope, self.token)
        self.assertEqual(raised.exception.code, 'license_revoked')
        self.service.revoke_license(self.scope, new.license_id)
        self.service.revoke_license(self.scope, new.license_id)
        self.assertEqual(self.service.summary(self.scope).license_status, 'revoked')
        with self.assertRaises(LicenseError):
            self.service.import_license(self.scope, signed_test_license(new, self.private))

    def test_multiprocess_import_keeps_coherent_state(self):
        ctx = multiprocessing.get_context('spawn')
        ready, start = ctx.Queue(), ctx.Event()
        tokens = [self.token, signed_test_license(replace(self.claims, license_id=UUID(int=8)), self.private)]
        processes = [ctx.Process(target=import_process, args=(str(self.root), self.public, token, ready, start))
                     for token in tokens]
        try:
            for process in processes:
                process.start()
            for _ in processes:
                self.assertTrue(ready.get(timeout=15))
            start.set()
            for process in processes:
                process.join(15)
                self.assertEqual(process.exitcode, 0)
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(5)
            ready.close()
        self.assertIn(self.service.require_valid(self.scope).license_id, (UUID(int=5), UUID(int=8)))
        state = json.loads((self.root / 'state.json').read_text())
        self.assertEqual(len(state['revoked_ids']), 1)

    def test_storage_corruption_and_failed_replace_are_closed(self):
        self.service.import_license(self.scope, self.token)
        with patch('src.infrastructure.license_local_store.os.replace', side_effect=OSError()):
            with self.assertRaises(LicenseError):
                self.service.import_license(self.scope, signed_test_license(
                    replace(self.claims, license_id=UUID(int=10)), self.private))
        self.assertEqual(self.service.require_valid(self.scope).license_id, UUID(int=5))
        (self.root / 'state.json').write_text('{}')
        self.assertEqual(self.service.summary(self.scope).license_status, 'storage_unavailable')
        with self.assertRaises(LicenseError):
            self.service.require_valid(self.scope)

    def test_license_audit_is_redacted(self):
        self.service.import_license(self.scope, self.token)
        self.service.revoke_license(self.scope, UUID(int=5))
        audit = (self.root / 'audit.jsonl').read_text()
        self.assertNotIn(self.token, audit)
        self.assertNotIn('PRIVATE KEY', audit)
        self.assertIn('license.imported', audit)
        self.assertIn('license.revoked', audit)
        self.assertNotIn(self.token, repr(self.store.read(self.scope)))

    def test_audit_projection_failure_keeps_grant_and_authoritative_event_together(self):
        self.service.import_license(self.scope, self.token)
        old_audit = (self.root / 'audit.jsonl').read_text()
        renewal = replace(self.claims, license_id=UUID(int=77))
        original_open = Path.open
        def fail_projection(path, *args, **kwargs):
            if path.name == 'audit.jsonl':
                raise OSError('audit unavailable')
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', fail_projection):
            result = self.service.import_license(self.scope, signed_test_license(renewal, self.private))
            self.assertEqual(result.license_id, renewal.license_id)
            state = json.loads((self.root / 'state.json').read_text())
            self.assertEqual(state['audit_events'][-1]['license_id'], str(renewal.license_id))
            self.service.revoke_license(self.scope, renewal.license_id)
            state = json.loads((self.root / 'state.json').read_text())
            self.assertEqual(state['audit_events'][-1]['event'], 'license.revoked')
        self.assertEqual((self.root / 'audit.jsonl').read_text(), old_audit)
        self.assertEqual(self.service.summary(self.scope).license_status, 'revoked')
        self.assertIn('license.renewed', (self.root / 'audit.jsonl').read_text())
        self.assertIn('license.revoked', (self.root / 'audit.jsonl').read_text())
        (self.root / 'audit.jsonl').write_bytes(b'\xff')
        self.assertEqual(self.service.summary(self.scope).license_status, 'revoked')
        self.assertIn('license.revoked', (self.root / 'audit.jsonl').read_text())
