import importlib
import types
import unittest
from unittest.mock import patch

from src.prompting import (
    ModuleAuditPromptProvider,
    PromptProviderUnavailable,
    load_prompt_provider,
)


def _valid_module() -> types.ModuleType:
    module = types.ModuleType("private_test_prompts")
    module.SYSTEM_NO_WEBSITE = "no-website system"
    module.SYSTEM_WEBSITE_AUDIT = "website-audit system"
    module.SYSTEM_PAGE_CLEAN = "page-clean system"
    module.build_no_website_prompt = lambda *args: "no-website user"
    module.build_website_audit_prompt = lambda *args: "website-audit user"
    module.build_page_clean_prompt = lambda *args: "page-clean user"
    return module


class PromptProviderTests(unittest.TestCase):
    def test_importing_auditor_does_not_load_private_bundle(self):
        import src.auditor as auditor_module

        with patch("src.prompting.importlib.import_module") as import_module:
            importlib.reload(auditor_module)

        import_module.assert_not_called()

    def test_private_module_is_loaded_only_at_explicit_runtime_boundary(self):
        private_module = _valid_module()
        with patch(
            "src.prompting.importlib.import_module",
            return_value=private_module,
        ) as import_module:
            provider = load_prompt_provider("vendor.private_prompts")

        import_module.assert_called_once_with("vendor.private_prompts")
        self.assertEqual(provider.system_no_website, "no-website system")
        self.assertEqual(
            provider.build_page_clean_prompt("url", "label", "content"),
            "page-clean user",
        )

    def test_missing_private_bundle_fails_closed_without_exposing_content(self):
        missing = ModuleNotFoundError("No module named 'vendor.private_prompts'")
        with (
            patch(
                "src.prompting.importlib.import_module",
                side_effect=missing,
            ),
            self.assertRaises(PromptProviderUnavailable) as caught,
        ):
            load_prompt_provider("vendor.private_prompts")

        self.assertIn("Bundle prompt proprietario", str(caught.exception))
        self.assertNotIn("vendor.private_prompts", str(caught.exception))

    def test_malformed_private_bundle_is_rejected(self):
        malformed = _valid_module()
        del malformed.build_website_audit_prompt

        provider = ModuleAuditPromptProvider(malformed, "malformed")
        with self.assertRaises(PromptProviderUnavailable) as caught:
            provider.validate()

        self.assertIn("build_website_audit_prompt()", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
