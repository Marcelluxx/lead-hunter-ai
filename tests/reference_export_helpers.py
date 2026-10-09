"""Ephemeral owner keys and real local licensing for reference-export tests."""
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.application.container import ApplicationContainer
from src.licensing.catalog import FeatureCatalog
from src.settings import ApplicationSettings
from tests.license_helpers import FakeClock, license_claims, signed_test_license, test_key_pair


class AvailableExportCatalog(FeatureCatalog):
    def all(self):
        return tuple(replace(item, module_status='available') if item.feature_id == 'export.no_website'
                     else item for item in super().all())


class ReferenceExportFixture:
    def __init__(self, testcase, *, available=True):
        temporary = tempfile.TemporaryDirectory()
        testcase.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.private, public = test_key_pair()
        trust = self.root / 'trust.json'
        trust.write_text(json.dumps({'version': 1, 'issuer': 'test-owner',
                                     'keys': {'test-key': public.decode()}}))
        self.environment = {'LEADHUNTER_LICENSE_ISSUER': 'test-owner',
                            'LEADHUNTER_LICENSE_TRUST_FILE': str(trust),
                            'LEADHUNTER_LICENSE_STATE_DIR': str(self.root / 'state')}
        environment = patch.dict(os.environ, self.environment)
        environment.start(); testcase.addCleanup(environment.stop)
        if available:
            catalog = patch('src.licensing.catalog.FeatureCatalog', AvailableExportCatalog)
            catalog.start(); testcase.addCleanup(catalog.stop)
        self.clock = FakeClock(10)
        timer = patch('src.application.license_clock.SystemClock.now_epoch', side_effect=self.clock.now_epoch)
        timer.start(); testcase.addCleanup(timer.stop)
        self.container = ApplicationContainer(ApplicationSettings())
        self.scope, self.licenses, self.access = self.container.build_local_license_service()
        self.claims = license_claims(scope=self.scope, features=('export.no_website',))
        self.token = signed_test_license(self.claims, self.private)

    def activate(self, claims=None):
        token = signed_test_license(claims or self.claims, self.private)
        self.licenses.import_license(self.scope, token)
        return token

    def service(self):
        return self.container.build_local_reference_export_service()
