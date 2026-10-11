import unittest
from decimal import Decimal

from src.domain.job_parameters import parse_job_parameters
from src.domain.job_pricing import JobPricePolicy, JobPriceError


class JobPricingTests(unittest.TestCase):
    def test_quote_is_server_configured_bounded_and_versioned(self):
        policy = JobPricePolicy(version='test-v1', google_request_ceiling='0.1', llm_request_ceiling='0.02')
        search = parse_job_parameters('discover.with_website', {'lat': 0, 'lng': 0, 'keywords': ['dentista'], 'max_leads': 2, 'max_pages': 3})
        quote = policy.quote(search)
        self.assertEqual(quote.google_calls, 18)
        self.assertEqual(quote.llm_calls, 24)
        self.assertEqual(quote.total, Decimal('2.280000'))
        self.assertEqual(quote.version, 'test-v1')
        self.assertEqual(quote.currency, 'EUR')
        self.assertEqual(policy.quote(parse_job_parameters('discover.no_website', search.payload)).llm_calls, 0)

    def test_missing_prices_block_only_required_providers(self):
        diagnostic = parse_job_parameters('diagnostic.website', {'url': 'https://site.test/', 'max_pages': 2})
        with self.assertRaisesRegex(JobPriceError, '^job_price_missing$'): JobPricePolicy(version='v1').quote(diagnostic)
        quote = JobPricePolicy(version='v1', llm_request_ceiling='0.01').quote(diagnostic)
        self.assertEqual(quote.google_calls, 0)
        self.assertEqual(quote.llm_calls, 9)
        self.assertEqual(quote.total, Decimal('0.09'))

    def test_invalid_prices_never_become_zero_or_nonfinite(self):
        for price in ['NaN', 'Infinity', '-1', '0', True, 'secret-sentinel', '0.0000001']:
            with self.subTest(price=price), self.assertRaisesRegex(JobPriceError, '^job_price_invalid$'):
                JobPricePolicy(version='v1', llm_request_ceiling=price)
        for version in ['', 'x' * 81]:
            with self.assertRaises(JobPriceError): JobPricePolicy(version=version)

    def test_environment_contains_no_client_cost_or_authority(self):
        policy = JobPricePolicy.from_mapping({'LEADHUNTER_JOB_PRICE_VERSION': 'owner-v2',
            'LEADHUNTER_JOB_GOOGLE_CALL_CEILING': '0.1', 'LEADHUNTER_JOB_LLM_CALL_CEILING': '0.02',
            'estimated_cost': '0', 'role': 'admin'})
        quote = policy.quote(parse_job_parameters('audit.website', {'urls': ['https://site.test/'], 'max_pages': 1}))
        self.assertEqual(quote.total, Decimal('0.12'))

