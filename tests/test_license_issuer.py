import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from src.domain.feature_licenses import LicenseError
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import LicenseVerifier
from tests.license_helpers import license_claims
from tools.license_issuer.keys import generate_issuer_keys
from tools.license_issuer.issuance import issue_license, parse_license_date
from tools.license_issuer.__main__ import main


class LicenseIssuerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.private = Path(tmp.name) / 'private.pem'
        self.public = Path(tmp.name) / 'public.pem'
        self.output = Path(tmp.name) / 'license.lh'

    def keys(self):
        generate_issuer_keys(private_path=self.private, public_path=self.public, passphrase=b'test-only')

    def issue(self):
        issue_license(license_claims(), private_path=self.private, passphrase=b'test-only',
                      kid='owner-test', output_path=self.output)

    def test_encrypted_key_and_issued_license_round_trip(self):
        self.keys()
        self.assertIn(b'ENCRYPTED PRIVATE KEY', self.private.read_bytes())
        with self.assertRaises((ValueError, TypeError)):
            serialization.load_pem_private_key(self.private.read_bytes(), password=None)
        self.assertIsNone(self.issue())
        verifier = LicenseVerifier(TrustedLicenseKeys('test-owner', {'owner-test': self.public.read_bytes()}),
                                    FeatureCatalog())
        self.assertEqual(verifier.verify(self.output.read_text(), scope=license_claims().scope,
                                         now_epoch=10).features, ('diagnostics.full',))

    def test_keygen_never_overwrites_existing_keys(self):
        self.keys()
        original = self.private.read_bytes()
        with self.assertRaises(LicenseError):
            self.keys()
        self.assertEqual(self.private.read_bytes(), original)

    def test_bad_passphrase_and_naive_dates_are_rejected(self):
        self.keys()
        for password in (b'', b'wrong'):
            with self.assertRaises(LicenseError):
                issue_license(license_claims(), private_path=self.private, passphrase=password,
                              kid='owner-test', output_path=self.output)
        with self.assertRaises(LicenseError):
            issue_license(license_claims(), private_path=self.public, passphrase=b'test-only',
                          kid='owner-test', output_path=self.output)
        for value in ('2026-10-09', '2026-10-09T10:00:00', 'bad', '2026-10-09T10:00:00.5Z'):
            with self.subTest(value=value), self.assertRaises(LicenseError):
                parse_license_date(value)
        self.assertEqual(parse_license_date('1970-01-01T01:00:10+01:00'), 10)

    def test_inspect_never_prints_token(self):
        self.keys()
        self.issue()
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(['inspect', '--license-file', str(self.output), '--public-key', str(self.public),
                           '--kid', 'owner-test', '--issuer', 'test-owner', '--installation-id',
                           str(license_claims().scope.installation_id), '--subject-kind', 'installation',
                           '--subject-id', str(license_claims().scope.subject_id)])
        self.assertEqual(result, 0)
        self.assertNotIn(self.output.read_text(), output.getvalue())
        self.assertIn('expired', output.getvalue())
