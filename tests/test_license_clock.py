import tempfile
import unittest
from pathlib import Path

from src.application.license_clock import GuardedClock
from src.domain.feature_licenses import LicenseError
from src.infrastructure.license_local_store import LocalLicenseStore
from tests.license_helpers import FakeClock


class LicenseClockTests(unittest.TestCase):
    def test_clock_rollback_uses_high_watermark(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalLicenseStore(Path(root))
            store.advance(1000)
            for now in (1000, 999, 701, 700):
                self.assertEqual(GuardedClock(FakeClock(now), store).now_epoch(), 1000)
            with self.assertRaises(LicenseError) as raised:
                GuardedClock(FakeClock(699), store).now_epoch()
            self.assertEqual(raised.exception.code, 'license_clock_regression')
            self.assertEqual(store.advance(800), 1000)
            self.assertEqual(store.advance(1001), 1001)
