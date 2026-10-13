import copy
import json
import unittest
from dataclasses import replace
from hashlib import sha256
from unittest.mock import patch

from bs4 import BeautifulSoup

from src.domain.audit import AuditValidationError
from src.domain.crawl import PageEvidence

URL = 'https://site.test/?token=PRIVATE_QUERY'
HTML = '''<html lang="it"><head><title>PRIVATE_TITLE</title><meta name="description" content="PRIVATE_DESCRIPTION">
<meta name="viewport" content="width=device-width"></head><body><h1>Studio</h1>
<img src="/decorative.png" alt=""><a href="mailto:mario.rossi@site.test">Scrivici</a>
<a href="/about"><img src="/logo.png" alt="Logo dello studio"></a>
<label for="email">Email</label><input id="email" type="email" value="PRIVATE_INPUT">
<label>Richiesta<textarea></textarea></label><span hidden id="select-label">Servizio</span>
<select aria-labelledby="select-label"><option>Consulenza</option></select>
<input type="text" aria-label="PRIVATE_LABEL"></body></html>'''


def markdown_evidence(url=URL, content_type='text/html'):
    return PageEvidence.from_content(requested_url=url, final_url=url, status_code=200,
        content_type=content_type, content='Contenuto indipendente dello studio. ' * 20)


class DomCheckTests(unittest.TestCase):
    def snapshot(self, html=HTML, evidence=None):
        try:
            from src.domain.dom_evidence import DomPageEvidence
        except ImportError:
            self.fail('DomPageEvidence capture is not implemented')
        return DomPageEvidence.capture(html, evidence or markdown_evidence())

    def inspect(self, html=HTML):
        try:
            from src.domain.dom_checks import inspect_dom
        except ImportError:
            self.fail('DOM inspector is not implemented')
        return inspect_dom(self.snapshot(html))

    def report(self):
        snapshot = self.snapshot(); checks, reason = self.inspect()
        return {'schema_version': 1, 'rules_version': '1', 'scope': 'collected_html_dom', 'method': 'dom_rules',
            'status': 'complete', 'coverage': {'eligible_pages': 1, 'inspected_pages': 1, 'inconclusive_pages': 0, 'omitted_pages': 0},
            'pages': [{'id': 'd_' + 'a' * 64, 'source_url': 'https://site.test/', 'dom_sha256': snapshot.dom_sha256,
                'markdown_sha256': snapshot.markdown_sha256, 'retrieved_at': snapshot.retrieved_at,
                'status': 'observed', 'reason': reason, 'checks': checks}]}

    def test_complete_dom_has_nine_scoped_rules_without_text_or_contact_payload(self):
        checks, reason = self.inspect()
        self.assertIsNone(reason)
        self.assertEqual(len(checks), 9)
        self.assertTrue(all(item['outcome'] == 'pass' for item in checks.values()))
        self.assertEqual(checks['image_alt_attribute'], {'outcome': 'pass', 'matched': 2, 'total': 2})
        self.assertEqual(checks['text_control_label_markup']['matched'], 4)
        self.assertEqual(checks['link_label_markup']['matched'], 2)
        self.assertNotIn('PRIVATE_', json.dumps(checks))
        self.assertNotIn('mario.rossi', json.dumps(checks))

    def test_snapshot_captures_original_hash_and_hides_private_html_and_url_in_repr(self):
        snapshot = self.snapshot()
        self.assertEqual(snapshot.dom_sha256, sha256(HTML.encode()).hexdigest())
        self.assertEqual(snapshot.markdown_sha256, markdown_evidence().content_sha256)
        self.assertEqual(snapshot.html, HTML)
        self.assertNotIn('PRIVATE_', repr(snapshot))

    def test_byte_limits_mime_and_missing_dom_do_not_become_absence(self):
        from src.domain.dom_checks import inspect_dom
        for html, evidence, expected in [(None, None, 'dom_unavailable'), ('', None, 'dom_unavailable'),
                ('é' * 125001, None, 'dom_too_large'), (HTML, markdown_evidence(content_type='text/plain'), 'unsupported_content_type'),
                (HTML, markdown_evidence(content_type=''), 'unsupported_content_type')]:
            snapshot = self.snapshot(html, evidence)
            self.assertIsNone(snapshot.html)
            checks, reason = inspect_dom(snapshot)
            self.assertEqual(checks, {}); self.assertEqual(reason, expected)
        self.assertIsNotNone(self.snapshot('X' * 250000).html)

    def test_partial_document_and_node_limit_are_inconclusive(self):
        for html, expected in [('<h1>Frammento</h1>', 'incomplete_document'),
            ('<noscript><html><head></head><body>Falso</body></html>', 'incomplete_document'),
            ('<html><head></head><body>Non terminato', 'incomplete_document'),
            ('<html><head></head><body>' + '<b></b>' * 20001 + '</body></html>', 'dom_node_limit')]:
            checks, reason = self.inspect(html)
            self.assertEqual(checks, {}); self.assertEqual(reason, expected)

    def test_hidden_and_inert_markup_cannot_supply_missing_predicates(self):
        html = '''<html><head></head><body><!-- <h1>Falso</h1> -->
        <script><h1>Falso</h1></script><template><img><h1>Falso</h1></template>
        <noscript><a href="mailto:test@site.test">Falso</a></noscript>
        <div hidden><h1>Falso</h1><input><img></div><div style="display: none"><img></div>
        <a href="mailto:test@site.test" aria-hidden="true">Contatti</a></body></html>'''
        checks, reason = self.inspect(html)
        self.assertIsNone(reason)
        self.assertEqual(checks['h1_text']['outcome'], 'fail')
        self.assertEqual(checks['contact_scheme_link']['outcome'], 'fail')
        self.assertEqual(checks['image_alt_attribute']['outcome'], 'not_applicable')
        self.assertEqual(checks['text_control_label_markup']['total'], 0)

    def test_document_end_ignores_comments_and_requires_a_real_html_close(self):
        checks, reason = self.inspect(HTML + '<!-- trailing comment -->')
        self.assertIsNone(reason)
        self.assertEqual(checks['title_text']['outcome'], 'pass')
        for raw_tag in ('script', 'textarea', 'title', 'template', 'noscript'):
            with self.subTest(raw_tag=raw_tag):
                checks, reason = self.inspect('<html><head></head><body><' + raw_tag + '>fake </html>')
                self.assertEqual(checks, {})
                self.assertEqual(reason, 'incomplete_document')

    def test_zero_width_text_and_placeholder_are_not_explicit_labels(self):
        html = '''<html lang="&#8203;"><head><title>&#8203;</title></head><body><h1> &#8203; </h1>
        <a href="/x">&#8203;</a><input placeholder="Email"><input aria-label="&#8203;"></body></html>'''
        checks, _ = self.inspect(html)
        for key in ['language_declaration', 'title_text', 'h1_text', 'link_label_markup', 'text_control_label_markup']:
            self.assertEqual(checks[key]['outcome'], 'fail', key)

    def test_duplicate_ids_do_not_prove_a_label_but_unique_hidden_reference_does(self):
        html = '''<html><head></head><body><label for="dup">Label</label>
        <input id="dup"><input id="dup"><span hidden id="unique">Label</span>
        <input aria-labelledby="unique"><input aria-labelledby="missing"></body></html>'''
        checks, _ = self.inspect(html)
        self.assertEqual(checks['text_control_label_markup'], {'outcome': 'fail', 'matched': 1, 'total': 4})

    def test_inert_element_ids_still_prevent_false_unique_label_associations(self):
        for tag in ('script', 'style', 'template', 'noscript'):
            html = ('<html><head></head><body><' + tag + ' id="x"></' + tag + '>'
                '<span id="x">Label</span><input aria-labelledby="x"><a href="/" aria-labelledby="x"></a>'
                '<' + tag + ' id="y"></' + tag + '><label for="y">Label</label><input id="y"></body></html>')
            with self.subTest(tag=tag):
                checks, reason = self.inspect(html)
                self.assertIsNone(reason)
                self.assertEqual(checks['text_control_label_markup'], {'outcome': 'fail', 'matched': 0, 'total': 2})
                self.assertEqual(checks['link_label_markup'], {'outcome': 'fail', 'matched': 0, 'total': 1})

    def test_admitted_inert_and_comment_siblings_have_linear_traversal_work(self):
        # Instrument dependency tree traversal, rather than imposing a CPU speed threshold.
        # Repeated sibling searches on admitted external markup must stay within a linear budget.
        work = [0]
        class CountedContents(list):
            def __iter__(self):
                for node in super().__iter__():
                    work[0] += 1
                    yield node
        def counted_soup(*args, **kwargs):
            soup = BeautifulSoup(*args, **kwargs)
            for tag in [soup, *soup.find_all(True)]:
                tag.contents = CountedContents(tag.contents)
            return soup
        count = 750
        html = ('<html><head></head><body>' + '<b></b>' * count
            + '<script>inert</script><!-- <h1>fake</h1> -->' * count + '</body></html>')
        with patch('src.domain.dom_checks.BeautifulSoup', side_effect=counted_soup):
            checks, reason = self.inspect(html)
        self.assertIsNone(reason)
        self.assertEqual(checks['h1_text']['outcome'], 'fail')
        self.assertLessEqual(work[0], 40 * (3 * count + 3))

    def test_alt_attribute_is_distinct_from_meaning_and_image_link_needs_nonempty_name(self):
        html = '''<html><head></head><body><a href="/a"><img alt=""></a>
        <a href="/b"><img alt="Nome"></a><img><input type="submit"><input type="hidden"></body></html>'''
        checks, _ = self.inspect(html)
        self.assertEqual(checks['image_alt_attribute'], {'outcome': 'fail', 'matched': 2, 'total': 3})
        self.assertEqual(checks['link_label_markup'], {'outcome': 'fail', 'matched': 1, 'total': 2})
        self.assertEqual(checks['text_control_label_markup']['outcome'], 'not_applicable')

    def test_malformed_urls_are_not_network_probes_or_pipeline_errors(self):
        html = '''<html><head></head><body><a href="https://[broken">Link</a>
        <a href="mailto:?subject=test">Contatti</a><a href="tel:">Telefono</a></body></html>'''
        checks, _ = self.inspect(html)
        self.assertEqual(checks['link_label_markup']['matched'], 3)
        self.assertEqual(checks['contact_scheme_link']['matched'], 0)

    def test_corrupted_snapshot_is_rejected_without_exposing_private_body(self):
        from src.domain.dom_checks import inspect_dom
        snapshot = replace(self.snapshot(), html=HTML + 'PRIVATE_CHANGED')
        with self.assertRaisesRegex(AuditValidationError, '^dom_evidence_invalid$'):
            inspect_dom(snapshot)

    def test_public_schema_rejects_forged_outcome_counts_metadata_or_extra_text(self):
        from src.domain.dom_checks import validate_dom_report
        report = self.report()
        self.assertEqual(validate_dom_report(report), report)
        invalid = [dict(report, schema_version=True), dict(report, rules_version='2'),
            dict(report, raw_html=HTML), dict(report, status='verified')]
        for key, value in [('matched', True), ('matched', 2), ('outcome', 'fail'), ('raw_label', 'PRIVATE_LABEL')]:
            candidate = copy.deepcopy(report); candidate['pages'][0]['checks']['title_text'][key] = value; invalid.append(candidate)
        candidate = copy.deepcopy(report); candidate['coverage']['eligible_pages'] = 2; invalid.append(candidate)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(AuditValidationError):
                validate_dom_report(value)
