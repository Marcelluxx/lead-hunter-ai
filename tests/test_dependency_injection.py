import unittest

from main import LeadHunterOrchestrator, create_orchestrator
from src.auditor import LeadAuditor
from src.scraper import LeadScraper
from src.settings import ApplicationSettings


class _FakeHttpClient:
    def post(self, *args, **kwargs):
        raise AssertionError("Il test non deve effettuare richieste HTTP.")

    def get(self, *args, **kwargs):
        raise AssertionError("Il test non deve effettuare richieste HTTP.")


class _FakeLlmClient:
    pass


class DependencyInjectionTests(unittest.TestCase):
    def test_orchestrator_uses_explicit_dependencies(self):
        scraper = object()
        auditor = object()

        orchestrator = LeadHunterOrchestrator(
            mode="with_website",
            scraper=scraper,
            auditor=auditor,
        )

        self.assertIs(orchestrator.scraper, scraper)
        self.assertIs(orchestrator.auditor, auditor)

    def test_no_website_orchestrator_does_not_require_an_auditor(self):
        scraper = object()

        orchestrator = LeadHunterOrchestrator(
            mode="no_website",
            scraper=scraper,
        )

        self.assertIs(orchestrator.scraper, scraper)
        self.assertIsNone(orchestrator.auditor)

    def test_composition_root_builds_only_dependencies_required_by_mode(self):
        settings = ApplicationSettings.from_mapping(
            {"GOOGLE_API_KEY": "google-test"}
        )

        orchestrator = create_orchestrator("no_website", settings)

        self.assertIsInstance(orchestrator.scraper, LeadScraper)
        self.assertIsNone(orchestrator.auditor)

    def test_scraper_uses_explicit_credentials_urls_and_http_client(self):
        http_client = _FakeHttpClient()
        scraper = LeadScraper(
            api_key="google-test",
            places_url="https://places.test/search",
            geocoding_url="https://places.test/geocode",
            field_mask="places.id",
            http_client=http_client,
        )

        self.assertIs(scraper.http_client, http_client)
        self.assertEqual(scraper.places_url, "https://places.test/search")
        self.assertEqual(scraper.geocoding_url, "https://places.test/geocode")
        self.assertEqual(scraper.headers["X-Goog-Api-Key"], "google-test")

    def test_auditor_uses_injected_client_and_models(self):
        client = _FakeLlmClient()
        auditor = LeadAuditor(
            api_key="",
            base_url="https://llm.test/v1",
            model="paid-model",
            model_free="free-model",
            client=client,
        )

        self.assertIs(auditor.client, client)
        self.assertEqual(auditor.model, "paid-model")
        self.assertEqual(auditor.model_free, "free-model")


if __name__ == "__main__":
    unittest.main()
