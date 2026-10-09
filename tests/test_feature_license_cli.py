import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from src.cli.feature_licenses import main
from src.domain.feature_licenses import LicenseScope, SubjectKind
from tests.license_helpers import license_claims, signed_test_license, test_key_pair


class FeatureLicenseCliTests(unittest.TestCase):
    def test_local_license_commands_need_no_provider_keys(self):
        with tempfile.TemporaryDirectory() as root:
            private, public = test_key_pair()
            trust = Path(root) / 'trust.json'
            trust.write_text(json.dumps({'version': 1, 'issuer': 'test-owner', 'keys': {'test-key': public.decode()}}))
            env = {'GOOGLE_API_KEY': '', 'OPENROUTER_API_KEY': '', 'LEADHUNTER_LICENSE_ISSUER': 'test-owner',
                   'LEADHUNTER_LICENSE_TRUST_FILE': str(trust), 'LEADHUNTER_LICENSE_STATE_DIR': str(Path(root) / 'state')}
            with patch.dict(os.environ, env, clear=True), patch('src.application.license_clock.SystemClock.now_epoch', return_value=10):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(['installation-id']), 0)
                identity = UUID(output.getvalue().strip())
                scope = LicenseScope(identity, SubjectKind.INSTALLATION, identity)
                path = Path(root) / 'license.lh'
                path.write_text(signed_test_license(license_claims(scope=scope), private))
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(['status']), 0)
                    self.assertEqual(main(['import', str(path)]), 0)
                    path.write_text('bad')
                    self.assertEqual(main(['import', str(path)]), 2)
                    self.assertEqual(main(['revoke', str(license_claims().license_id)]), 0)
                    path.write_text('x' * 16385)
                    self.assertEqual(main(['import', str(path)]), 2)
