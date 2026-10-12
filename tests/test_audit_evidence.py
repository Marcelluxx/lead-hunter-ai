import copy
import json
import unittest
from datetime import datetime, timezone
from hashlib import sha256

from src.domain.audit import AuditValidationError

URL = 'https://site.test/contatti?token=SECRET_SENTINEL'
QUOTE = 'Il nostro studio offre consulenza alle imprese.'
PAGES = {URL: 'Benvenuti. ' * 30 + QUOTE + ' Scrivi a mario.rossi@site.test oppure +39 333 1234567. api_key=PRIVATE_KEY'}
TIME = datetime(2026, 10, 12, tzinfo=timezone.utc)


def finding(evidence_id, quote=QUOTE, **changes):
    return {'category': 'usability', 'severity': 'medium', 'description': 'Valutare il percorso contatti.',
        'citations': [{'evidence_id': evidence_id, 'quote': quote}], **changes}


class AuditEvidenceTests(unittest.TestCase):
    def evidence(self, pages=PAGES):
        try:
            from src.domain.audit_evidence import AuditEvidenceSet
        except ImportError:
            self.fail('AuditEvidenceSet contract is not implemented')
        return AuditEvidenceSet.from_pages(pages, collected_at=TIME)

    def entry(self, context):
        return json.loads(context.to_prompt_payload())['pages'][0]

    def test_real_quote_is_grounded_but_never_proves_model_diagnosis(self):
        context = self.evidence()
        item = self.entry(context)
        report = context.validate_findings({'findings': [finding(item['evidence_id'])]})
        self.assertEqual(report['schema_version'], 1)
        self.assertEqual(report['status'], 'inconclusive')
        result = report['findings'][0]
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(result['method'], 'llm_observation')
        citation = result['citations'][0]
        self.assertEqual(citation['status'], 'matched')
        self.assertEqual(citation['quote_sha256'], sha256(QUOTE.encode()).hexdigest())
        self.assertEqual(PAGES[URL][citation['start']:citation['end']], QUOTE)
        self.assertEqual(report['evidence'][0]['content_sha256'], sha256(PAGES[URL].encode()).hexdigest())
        self.assertEqual(context.verify_report(report), report)

    def test_missing_findings_is_explicit_legacy_and_empty_is_not_a_clean_bill(self):
        context = self.evidence()
        self.assertEqual(context.validate_findings({})['status'], 'legacy_uncited')
        self.assertEqual(context.validate_findings({'findings': []})['status'], 'inconclusive')

    def test_fabricated_wrong_page_normalized_or_out_of_catalog_quotes_are_rejected(self):
        extra_url = 'https://site.test/about'
        context = self.evidence({**PAGES, extra_url: 'Servizi. ' * 30 + 'São Paulo: caffè e consulenza aziendale.'})
        first, second = json.loads(context.to_prompt_payload())['pages']
        invalid = [finding('unknown'), finding(first['evidence_id'], 'Questa frase non è nel sito originale.'),
            finding(second['evidence_id']), finding(second['evidence_id'], 'Sao Paulo: caffe e consulenza aziendale.')]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(AuditValidationError):
                context.validate_findings({'findings': [value]})
        long = self.evidence({URL: 'A' * 5100 + QUOTE})
        with self.assertRaises(AuditValidationError):
            long.validate_findings({'findings': [finding(self.entry(long)['evidence_id'])]})
        report = context.validate_findings({'findings': [finding(second['evidence_id'], 'São Paulo: caffè e consulenza aziendale.')]})
        self.assertEqual(report['findings'][0]['citations'][0]['excerpt'], 'São Paulo: caffè e consulenza aziendale.')

    def test_finding_authority_types_limits_and_duplicates_are_rejected_safely(self):
        context = self.evidence(); good = finding(self.entry(context)['evidence_id'])
        invalid = [None, {}, [dict(good, status='verified')], [dict(good, confidence=1)],
            [dict(good, source_url='https://evil.test')], [dict(good, severity='critical')],
            [dict(good, description='X' * 1001)], [dict(good, category=False)],
            [dict(good, citations=[])], [dict(good, citations=good['citations'] * 4)],
            [dict(good, citations=good['citations'] * 2)], [good, good]]
        invalid += [[dict(good, citations=[{'evidence_id': self.entry(context)['evidence_id'], 'quote': q}])]
            for q in ['X' * 19, 'X' * 501, 42]]
        invalid += [[dict(good, description='Finding ' + str(i)) for i in range(21)]]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(AuditValidationError) as raised:
                context.validate_findings({'findings': values})
            self.assertNotIn('SECRET_SENTINEL', str(raised.exception))

    def test_public_projection_redacts_contact_secrets_and_query_without_losing_original_hash(self):
        context = self.evidence()
        quote = 'Scrivi a mario.rossi@site.test oppure +39 333 1234567. api_key=PRIVATE_KEY'
        report = context.validate_findings({'findings': [finding(self.entry(context)['evidence_id'], quote,
            description='Contatta mario.rossi@site.test al +39 333 1234567')]})
        public = json.dumps(report, ensure_ascii=False)
        for secret in ['mario.rossi', '333 1234567', 'PRIVATE_KEY', 'SECRET_SENTINEL']:
            self.assertNotIn(secret, public)
        self.assertIn('[REDACTED_EMAIL]', public)
        self.assertEqual(report['evidence'][0]['source_url'], 'https://site.test/contatti')
        self.assertEqual(context.verify_report(report), report)
        self.assertNotIn(PAGES[URL], public)

    def test_output_metadata_mutation_is_rejected_and_timestamp_is_trusted_input(self):
        context = self.evidence()
        report = context.validate_findings({'findings': [finding(self.entry(context)['evidence_id'])]})
        for location, key, value in [('citation', 'start', 0), ('citation', 'quote_sha256', 'a' * 64),
                ('citation', 'excerpt', 'Invented citation text.'), ('finding', 'status', 'verified'),
                ('evidence', 'content_sha256', 'a' * 64)]:
            bad = copy.deepcopy(report)
            target = bad['findings'][0]['citations'][0] if location == 'citation' else (
                bad['findings'][0] if location == 'finding' else bad['evidence'][0])
            target[key] = value
            with self.subTest(key=key), self.assertRaises(AuditValidationError):
                context.verify_report(bad)
        self.assertEqual(report['evidence'][0]['retrieved_at'], TIME.isoformat())

    def test_catalog_bounds_invalid_pages_and_report_storage_bounds(self):
        context = self.evidence({f'https://site.test/{i}': 'X' * 6000 for i in range(20)})
        payload = json.loads(context.to_prompt_payload())
        self.assertLessEqual(sum(len(x['content']) for x in payload['pages']), 12000)
        self.assertTrue(all(len(x['content']) <= 5000 for x in payload['pages']))
        with self.assertRaises(AuditValidationError):
            self.evidence({f'https://site.test/{i}': 'X' * 6000 for i in range(21)})
        from src.domain.audit_evidence import validate_public_report
        report = self.evidence().validate_findings({})
        for invalid in [dict(report, raw_prompt='SECRET'), dict(report, schema_version=True),
                dict(report, status='verified'), dict(report, findings=[{'description': 'X' * 25000}])]:
            with self.assertRaises(AuditValidationError):
                validate_public_report(invalid)
