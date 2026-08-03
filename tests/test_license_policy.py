import unittest
from datetime import date

from scripts.check_licenses import validate_licenses


class LicensePolicyTests(unittest.TestCase):
    def setUp(self):
        self.sbom = {
            "components": [
                {"type": "library", "name": "safe-package"},
                {"type": "library", "name": "metadata-gap"},
            ]
        }
        self.policy = {
            "allowed_license_atoms": ["MIT", "Apache-2.0"],
            "review_required_atoms": [],
            "package_overrides": {
                "metadata-gap": {
                    "license": "MIT",
                    "versions": ["1.2.3"],
                    "sources": {"1.2.3": "https://example.test/license"},
                    "reviewed": "2026-01-01",
                    "expires": "2027-01-01",
                    "reason": "Upstream wheel omits its declared license metadata.",
                }
            },
        }

    def test_accepts_allowlisted_license_and_bounded_override(self):
        result = validate_licenses(
            [
                {"Name": "safe_package", "Version": "2.0", "License": "Apache-2.0"},
                {"Name": "metadata-gap", "Version": "1.2.3", "License": "UNKNOWN"},
                {"Name": "ci-only-tool", "Version": "1", "License": "UNKNOWN"},
            ],
            self.sbom,
            self.policy,
            today=date(2026, 8, 3),
        )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["checked_packages"], 2)
        self.assertTrue(result["packages"][0]["override_applied"])

    def test_rejects_unknown_uncovered_and_expired_licenses(self):
        inventory = [
            {"Name": "safe-package", "Version": "2.0", "License": "GPL-3.0"},
            {"Name": "metadata-gap", "Version": "1.2.4", "License": "UNKNOWN"},
        ]

        result = validate_licenses(
            inventory,
            self.sbom,
            self.policy,
            today=date(2027, 1, 2),
        )

        self.assertEqual(result["status"], "fail")
        self.assertEqual(len(result["failures"]), 2)

        expired = validate_licenses(
            [{"Name": "metadata-gap", "Version": "1.2.3", "License": "UNKNOWN"}],
            self.sbom,
            self.policy,
            today=date(2027, 1, 2),
        )
        self.assertIn("expired", expired["failures"][0])


if __name__ == "__main__":
    unittest.main()
