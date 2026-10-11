import math
import unittest
from unittest.mock import patch

from src.domain.job_parameters import parse_job_parameters, JobParameterError


class JobParameterTests(unittest.TestCase):
    def search(self, **changes):
        return {'lat': 0, 'lng': 0, 'keywords': [' Dentista ', 'dentista', ' Clinica '], **changes}

    def test_search_modes_normalize_and_keep_zero_coordinates(self):
        for kind in ['discover.no_website', 'discover.with_website']:
            parsed = parse_job_parameters(kind, self.search())
            self.assertEqual(parsed.kind, kind)
            self.assertEqual(parsed.payload['keywords'], ['Dentista', 'Clinica'])
            self.assertEqual(parsed.payload['lat'], 0)
            self.assertEqual(parsed.payload['lng'], 0)
            self.assertEqual(parsed.payload['schema_version'], 1)
            self.assertEqual(parsed.payload['max_leads'], 20)
            self.assertEqual(parsed.required_features, ())
            changed = parsed.payload; changed['lat'] = 90
            self.assertEqual(parsed.payload['lat'], 0)

    def test_rating_criteria_only_adds_reserved_feature_in_both_modes(self):
        for kind in ['discover.no_website', 'discover.with_website']:
            parsed = parse_job_parameters(kind, self.search(rating_filters={'min_rating': 3.9, 'max_reviews': 100}))
            self.assertEqual(parsed.required_features, ('discovery.rating_filters',))
            self.assertEqual(parsed.payload['rating_filters']['min_rating'], 3.9)

    def test_audit_and_diagnostic_urls_normalize_without_network(self):
        with patch('src.security.url_policy.SafeUrlPolicy._resolve_public_addresses') as dns:
            audit = parse_job_parameters('audit.website', {'urls': ['https://Example.COM#fragment', 'https://example.com/']})
            dns.assert_not_called()
        self.assertEqual(audit.payload['urls'], ['https://example.com/'])
        self.assertEqual(audit.required_features, ())
        diagnostic = parse_job_parameters('diagnostic.website', {'url': 'https://example.com/', 'retention_hours': 4})
        self.assertEqual(diagnostic.required_features, ('diagnostics.full',))
        self.assertEqual(diagnostic.payload['retention_hours'], 4)

    def test_strict_invalid_numbers_ranges_and_work_limits(self):
        invalid = [self.search(lat=True), self.search(lng='0'), self.search(lat=math.nan),
            self.search(lat=math.inf), self.search(lat=-91), self.search(lng=181), self.search(keywords=[]),
            self.search(keywords=[' ']), self.search(keywords=['x' * 101]), self.search(keywords=['a'] * 6),
            self.search(max_pages=0), self.search(max_pages=21), self.search(max_pages=True),
            self.search(max_leads=101), self.search(max_leads=0), self.search(max_leads=100, max_pages=20),
            self.search(schema_version=True), self.search(schema_version=2), self.search(token_mode='invalid'),
            self.search(rating_filters={'min_rating': True, 'max_reviews': 100}),
            self.search(rating_filters={'min_rating': 5.1, 'max_reviews': 100}),
            self.search(rating_filters={'min_rating': 3.9, 'max_reviews': False})]
        for parameters in invalid:
            with self.subTest(parameters=parameters), self.assertRaisesRegex(JobParameterError, '^job_parameters_invalid$'):
                parse_job_parameters('discover.with_website', parameters)

    def test_unknown_kind_extra_authority_secrets_and_provider_payload_fail_closed(self):
        for key, value in [('role', 'admin'), ('mfa_verified', True), ('api_key', 'secret-sentinel'),
                           ('output', '../../private'), ('estimated_cost', 0), ('created_by', 'forged')]:
            with self.subTest(key=key), self.assertRaisesRegex(JobParameterError, '^job_parameters_invalid$') as error:
                parse_job_parameters('discover.no_website', self.search(**{key: value}))
            self.assertNotIn('secret-sentinel', str(error.exception))
        with self.assertRaisesRegex(JobParameterError, '^job_kind_unsupported$'):
            parse_job_parameters('unregistered', {})
        with self.assertRaisesRegex(JobParameterError, '^provider_payload_not_allowed$'):
            parse_job_parameters('discover.no_website', self.search(places=[{'displayName': 'secret-sentinel'}]))

    def test_invalid_url_syntax_credentials_and_protocols_rejected(self):
        for url in ['not-a-url', 'file:///etc/passwd', 'https://user:password@site.test/',
                    'https://site.test:8443/', 'https://site.test/\nsecret', 'https://[broken/', 'https://']:
            for kind, parameters in [('audit.website', {'urls': [url]}), ('diagnostic.website', {'url': url})]:
                with self.subTest(url=url, kind=kind), self.assertRaisesRegex(JobParameterError, '^job_parameters_invalid$'):
                    parse_job_parameters(kind, parameters)
        for parameters in [{'url': 'https://site.test', 'retention_hours': 0},
                           {'url': 'https://site.test', 'retention_hours': 169},
                           {'url': 'https://site.test', 'retention_hours': True}]:
            with self.assertRaises(JobParameterError): parse_job_parameters('diagnostic.website', parameters)

    def test_non_dict_and_deep_untrusted_values_return_safe_error(self):
        for parameters in [None, [], {'urls': 'https://site.test/'}, {'urls': ['x'] * 21}]:
            with self.assertRaises(JobParameterError): parse_job_parameters('audit.website', parameters)
        nested = {}
        for _ in range(1200): nested = {'x': nested}
        with self.assertRaises(JobParameterError): parse_job_parameters('audit.website', nested)
