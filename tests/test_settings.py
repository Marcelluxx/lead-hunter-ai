import importlib
import unittest

from src.settings import (
    ApplicationSettings,
    SettingsValidationError,
    SettingsValueError,
)


class ApplicationSettingsTests(unittest.TestCase):
    def test_importing_config_and_providers_does_not_require_credentials(self):
        for module_name in ("src.config", "src.scraper", "src.auditor"):
            module = importlib.import_module(module_name)
            importlib.reload(module)

    def test_reports_all_missing_credentials_at_the_explicit_boundary(self):
        settings = ApplicationSettings.from_mapping({})

        with self.assertRaises(SettingsValidationError) as caught:
            settings.require_pipeline("with_website")

        self.assertEqual(
            caught.exception.missing,
            ("GOOGLE_API_KEY", "OPENROUTER_API_KEY"),
        )

    def test_mapping_is_normalized_without_reading_process_environment(self):
        settings = ApplicationSettings.from_mapping(
            {
                "GOOGLE_API_KEY": "  google-test  ",
                "OPENROUTER_API_KEY": " openrouter-test ",
                "LLM_MODEL": " vendor/model ",
                "TOKEN_MODE": " optimized ",
            }
        )

        self.assertEqual(settings.google_api_key, "google-test")
        self.assertEqual(settings.openrouter_api_key, "openrouter-test")
        self.assertEqual(settings.llm_model, "vendor/model")
        self.assertEqual(settings.token_mode, "optimized")

    def test_no_website_pipeline_requires_only_google(self):
        settings = ApplicationSettings.from_mapping(
            {"GOOGLE_API_KEY": "google-test"}
        )

        settings.require_pipeline("no_website")

    def test_rejects_invalid_token_mode_and_insecure_provider_urls(self):
        with self.assertRaises(SettingsValueError):
            ApplicationSettings.from_mapping({"TOKEN_MODE": "turbo"})

        with self.assertRaises(SettingsValueError):
            ApplicationSettings.from_mapping(
                {"OPENROUTER_BASE_URL": "http://llm.internal/v1"}
            )


if __name__ == "__main__":
    unittest.main()
