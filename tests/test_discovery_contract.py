import unittest
from dataclasses import asdict
import requests

from src.domain.discovery import DiscoveryQuery, TransientCandidate
from src.providers.discovery.google_places import (
    DiscoveryProviderError,
    GooglePlacesDiscoveryProvider,
)


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "places": [
                {
                    "id": "place-1",
                    "displayName": {"text": "Example"},
                    "websiteUri": "https://example.test",
                    "formattedAddress": "must never leave adapter",
                    "reviews": [{"text": {"text": "forbidden"}}],
                }
            ]
        }


class _HttpClient:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response()


class _TimeoutClient:
    def __init__(self):
        self.attempts = 0

    def post(self, *args, **kwargs):
        self.attempts += 1
        raise requests.Timeout("secret response must not escape")


class DiscoveryContractTests(unittest.TestCase):
    def test_google_adapter_reduces_raw_response_to_transient_contract(self):
        client = _HttpClient()
        provider = GooglePlacesDiscoveryProvider(
            api_key="test",
            places_url="https://places.test/search",
            field_mask="places.id,places.displayName,places.websiteUri,places.attributions",
            http_client=client,
            grid_size=1,
            inter_request_delay_s=0,
        )
        batch = provider.discover(DiscoveryQuery("dentista", 45.0, 9.0))

        self.assertEqual(len(batch.candidates), 1)
        candidate = batch.candidates[0]
        self.assertIsInstance(candidate, TransientCandidate)
        self.assertTrue(candidate.is_transient_provider_content)
        serialized_for_test_only = asdict(candidate)
        self.assertNotIn("formattedAddress", serialized_for_test_only)
        self.assertNotIn("reviews", serialized_for_test_only)
        self.assertEqual(client.calls[0][1]["timeout"], 15.0)

    def test_field_mask_never_requests_reviews_ratings_addresses_or_phone(self):
        provider = GooglePlacesDiscoveryProvider(
            api_key="test",
            places_url="https://places.test/search",
            field_mask="places.id,places.displayName,places.websiteUri,places.attributions",
            http_client=_HttpClient(),
            grid_size=1,
            inter_request_delay_s=0,
        )
        mask = provider.headers["X-Goog-FieldMask"]
        for forbidden in ("reviews", "rating", "Address", "Phone"):
            self.assertNotIn(forbidden, mask)

    def test_timeout_is_bounded_and_safely_classified(self):
        client = _TimeoutClient()
        provider = GooglePlacesDiscoveryProvider(
            api_key="secret-api-key",
            places_url="https://places.test/search",
            field_mask="places.id",
            http_client=client,
            grid_size=1,
            inter_request_delay_s=0,
            max_attempts=2,
        )
        with self.assertRaisesRegex(DiscoveryProviderError, "provider_timeout") as raised:
            provider.discover(DiscoveryQuery("dentista", 45.0, 9.0))
        self.assertEqual(client.attempts, 2)
        self.assertNotIn("secret-api-key", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
