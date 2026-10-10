import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.licensing.settings import LicenseSettings
from src.settings import SettingsError
from tests.license_helpers import test_key_pair


class FeatureLicenseSettingsTests(unittest.TestCase):
    def test_empty_compose_trust_path_keeps_server_licensing_unconfigured(self):
        from src.web.settings import ServerSettings
        with patch.dict(os.environ, {}, clear=True):
            settings = ServerSettings(_env_file=None,
                database_url='postgresql+psycopg://unused', master_key_base64='unused',
                suppression_hmac_key_base64='unused', jwt_private_key_file='unused',
                jwt_public_key_file='unused', license_trust_file='', installation_id='')
            self.assertIsNone(settings.license_configuration().trust_file)

    def test_trust_file_rejects_private_duplicate_and_unexpected_material(self):
        private, public = test_key_pair()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'trust.json'
            settings = LicenseSettings('test-owner', path, Path(root), None)
            valid = {'version': 1, 'issuer': 'test-owner', 'keys': {'test-key': public.decode()}}
            path.write_text(json.dumps(valid))
            self.assertIsNotNone(settings.load_trusted_keys().resolve('test-key'))
            for data in ({**valid, 'extra': 1}, {**valid, 'version': True}, {**valid, 'issuer': 'other'},
                         {**valid, 'keys': {'test-key': private.decode()}}):
                path.write_text(json.dumps(data))
                with self.assertRaises(SettingsError):
                    settings.load_trusted_keys()
            path.write_text('{"version":1,"version":1,"issuer":"test-owner","keys":{}}')
            with self.assertRaises(SettingsError):
                settings.load_trusted_keys()

    def test_unconfigured_base_is_valid_and_server_id_required_only_when_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = LicenseSettings.from_environment()
            self.assertIsNone(settings.trust_file)
            self.assertTrue(settings.local_state_dir.is_absolute())
            settings.validate_server()
        with patch.dict(os.environ, {'LEADHUNTER_LICENSE_TRUST_FILE': 'configured.json'}, clear=True):
            with self.assertRaises(SettingsError):
                LicenseSettings.from_environment().validate_server()
