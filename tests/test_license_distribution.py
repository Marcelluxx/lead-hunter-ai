import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from scripts.check_customer_image import check_customer_image


class CustomerImageGateTests(unittest.TestCase):
    def test_public_dependency_certificates_do_not_allow_private_licensing_keys(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            public = root / '.venv/lib/python3.11/site-packages/certifi/cacert.pem'
            public.parent.mkdir(parents=True)
            public.write_text('-----BEGIN CERTIFICATE-----\npublic dependency fixture')
            check_customer_image(root)
            private = root / 'license.pem'
            private.write_text('synthetic-private-file')
            with self.assertRaises(SystemExit):
                check_customer_image(root)
            private.unlink()
            public.write_text('-----BEGIN PRIVATE KEY-----\nsynthetic fixture')
            with self.assertRaises(SystemExit):
                check_customer_image(root)


@unittest.skipUnless(os.getenv('RUN_DISTRIBUTION_BUILD') == '1', 'Docker distribution build not requested')
class LicenseDistributionTests(unittest.TestCase):
    def test_customer_build_excludes_issuer_and_private_state(self):
        tag = 'leadhunter-context-test:' + uuid4().hex
        container = None
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            shutil.copy('.dockerignore', root / '.dockerignore')
            (root / 'Dockerfile').write_text('FROM scratch\nCOPY . /app\nCMD ["/app/public.txt"]\n')
            forbidden = ['tools/license_issuer/keys.py', '.secrets/private', '.leadhunter-state/state.json',
                         'private.pem', 'private.key', 'private.p12', 'private.pfx',
                         'nested/private.pem', 'src/prompts.py']
            for name in forbidden + ['public.txt']:
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('synthetic-distribution-probe')
            try:
                subprocess.run(['docker', 'build', '-q', '-t', tag, str(root)],
                               check=True, capture_output=True, timeout=120)
                container = subprocess.check_output(['docker', 'create', tag], text=True).strip()
                archive = root / 'image.tar'
                subprocess.run(['docker', 'export', '-o', str(archive), container],
                               check=True, capture_output=True, timeout=30)
                with tarfile.open(archive) as image:
                    paths = set(image.getnames())
                self.assertIn('app/public.txt', paths)
                for name in forbidden:
                    with self.subTest(name=name):
                        self.assertNotIn('app/' + name, paths)
            finally:
                if container:
                    subprocess.run(['docker', 'rm', container], capture_output=True, timeout=30)
                subprocess.run(['docker', 'image', 'rm', tag], capture_output=True, timeout=30)
