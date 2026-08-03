import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.security.geolocation import GeolocationError, lookup_approximate_location
from src.security.privacy import purge_expired_diagnostic_files, redact_sensitive_text


class _AllowingPolicy:
    def validate(self, url, *, allowed_hosts=None):
        return SimpleNamespace(normalized_url=url)


class _Response:
    status_code = 200
    content = b'{"success":true,"latitude":45.4,"longitude":9.1}'

    def json(self):
        return {
            "success": True,
            "latitude": 45.4,
            "longitude": 9.1,
            "ip": "203.0.113.10",
        }


class PrivacyControlTests(unittest.TestCase):
    def test_redacts_emails_ips_and_credentials(self):
        message = (
            "email mario@example.com ip 8.8.8.8 "
            "Bearer abc.def token=secret123 https://x.test/?api_key=visible"
        )

        redacted = redact_sensitive_text(message)

        self.assertNotIn("mario@example.com", redacted)
        self.assertNotIn("8.8.8.8", redacted)
        self.assertNotIn("abc.def", redacted)
        self.assertNotIn("secret123", redacted)
        self.assertNotIn("visible", redacted)

    def test_geolocation_is_https_only_and_returns_no_ip(self):
        calls = []

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return _Response()

        location = lookup_approximate_location(
            endpoint="https://ipwho.is/",
            http_get=fake_get,
            url_policy=_AllowingPolicy(),
        )

        self.assertEqual(location.to_public_dict(), {"lat": 45.4, "lng": 9.1})
        self.assertFalse(calls[0][1]["allow_redirects"])
        self.assertEqual(calls[0][1]["timeout"], (2, 4))

        with self.assertRaises(GeolocationError):
            lookup_approximate_location(
                endpoint="http://ipwho.is/",
                http_get=fake_get,
                url_policy=_AllowingPolicy(),
            )

    def test_purges_only_expired_regular_files_inside_root(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_file = root / "old.txt"
            recent_file = root / "recent.txt"
            old_file.write_text("old", encoding="utf-8")
            recent_file.write_text("recent", encoding="utf-8")
            os.utime(old_file, (now - 7200, now - 7200))

            removed = purge_expired_diagnostic_files(root, 1, now=now)

            self.assertEqual(removed, 1)
            self.assertFalse(old_file.exists())
            self.assertTrue(recent_file.exists())


if __name__ == "__main__":
    unittest.main()
