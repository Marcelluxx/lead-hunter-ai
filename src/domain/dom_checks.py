"""Versioned, narrowly scoped DOM markup predicates; no semantic site verdict."""
import json
import re
import unicodedata
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .audit import AuditValidationError
from .audit_evidence import public_evidence_url
from .dom_evidence import MAX_DOM_BYTES

RULES_VERSION = '1'
RULE_IDS = ('title_text', 'meta_description', 'h1_text', 'language_declaration', 'viewport_declaration',
    'image_alt_attribute', 'link_label_markup', 'text_control_label_markup', 'contact_scheme_link')
PRESENCE_RULES = frozenset(RULE_IDS) - {'image_alt_attribute', 'link_label_markup', 'text_control_label_markup'}
DOM_REASONS = frozenset(('dom_not_collected', 'dom_unavailable', 'dom_too_large', 'unsupported_content_type',
    'page_not_auditable', 'incomplete_document', 'dom_node_limit', 'analysis_budget'))
MAX_REPORT_BYTES = 24000
MAX_ANALYSIS_BYTES = 2000000
MAX_DOM_NODES = 20000
_INLINE_HIDDEN = re.compile(r'(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)(?:\s*!important)?\s*(?:;|$)', re.I)


def _need(condition, code='dom_report_invalid'):
    if not condition:
        raise AuditValidationError(code)


def _object(value, keys):
    _need(isinstance(value, dict) and set(value) == set(keys))


def _text(value):
    return isinstance(value, str) and any(not char.isspace() and unicodedata.category(char) not in ('Cc', 'Cf') for char in value)


def metric(matched, total):
    return {'outcome': 'not_applicable' if total == 0 else 'pass' if matched == total else 'fail',
        'matched': matched, 'total': total}


def inspect_dom(snapshot):
    if snapshot.failure_code is not None:
        _need(snapshot.failure_code in DOM_REASONS and snapshot.html is None, 'dom_evidence_invalid')
        return {}, snapshot.failure_code
    _need(isinstance(snapshot.html, str), 'dom_evidence_invalid')
    encoded = snapshot.html.encode('utf-8', errors='replace')
    _need(len(encoded) <= MAX_DOM_BYTES and sha256(encoded).hexdigest() == snapshot.dom_sha256, 'dom_evidence_invalid')
    soup = BeautifulSoup(snapshot.html, 'html.parser')
    root = soup.find('html', recursive=False)
    if root is None or root.find('head', recursive=False) is None or root.find('body', recursive=False) is None or not re.search(r'</html\s*>\s*$', snapshot.html, re.I):
        return {}, 'incomplete_document'
    if len(soup.find_all(True)) > MAX_DOM_NODES:
        return {}, 'dom_node_limit'
    for comment in soup.find_all(string=lambda item: isinstance(item, Comment)):
        comment.extract()
    for tag in soup.find_all(('script', 'style', 'template', 'noscript')):
        tag.decompose()
    head, body = root.find('head', recursive=False), root.find('body', recursive=False)
    nodes = list(soup.descendants)
    visible = {}; nearest_label = {}; ids = {}; labels = []
    for node in nodes:
        parent_id = id(node.parent)
        if isinstance(node, Tag):
            hidden = node.has_attr('hidden') or str(node.get('aria-hidden', '')).casefold() == 'true' or _INLINE_HIDDEN.search(str(node.get('style', '')))
            visible[id(node)] = visible.get(parent_id, True) and not hidden
            nearest_label[id(node)] = node if node.name == 'label' else nearest_label.get(parent_id)
            identifier = node.get('id')
            if isinstance(identifier, str) and identifier:
                ids.setdefault(identifier, []).append(node)
            if node.name == 'label': labels.append(node)
        else:
            visible[id(node)] = visible.get(parent_id, True)
    all_text = {}; exposed_text = {}; graphics = {}
    for node in reversed(nodes):
        node_id, parent_id = id(node), id(node.parent)
        if isinstance(node, NavigableString) and _text(str(node)):
            all_text[node_id] = True
            if visible[node_id]: exposed_text[node_id] = True
        if isinstance(node, Tag) and node.name == 'img' and visible[node_id] and _text(node.get('alt')):
            graphics[node_id] = True
        if all_text.get(node_id): all_text[parent_id] = True
        if visible.get(parent_id, True):
            if exposed_text.get(node_id): exposed_text[parent_id] = True
            if graphics.get(node_id): graphics[parent_id] = True
    label_for = {label.get('for') for label in labels if all_text.get(id(label)) and len(ids.get(label.get('for'), [])) == 1}
    def aria_name(tag):
        if _text(tag.get('aria-label')): return True
        references = str(tag.get('aria-labelledby', '')).split()
        return any(len(ids.get(ref, [])) == 1 and all_text.get(id(ids[ref][0]), False) for ref in references)
    body_tags = [tag for tag in body.descendants if isinstance(tag, Tag) and visible[id(tag)]]
    images = [tag for tag in body_tags if tag.name == 'img']
    anchors = [tag for tag in body_tags if tag.name == 'a' and tag.has_attr('href')]
    controls = [tag for tag in body_tags if tag.name in ('textarea', 'select') or
        (tag.name == 'input' and str(tag.get('type') or 'text').casefold() in ('text', 'email', 'password', 'tel', 'search', 'url', 'number'))]
    linked = sum(bool(exposed_text.get(id(tag)) or graphics.get(id(tag)) or aria_name(tag) or _text(tag.get('title'))) for tag in anchors)
    labeled = sum(bool(aria_name(tag) or tag.get('id') in label_for or
        (nearest_label.get(id(tag)) is not None and all_text.get(id(nearest_label[id(tag)])))) for tag in controls)
    contact = False
    for tag in anchors:
        try:
            target = urlsplit(str(tag['href']))
            if target.scheme.casefold() in ('mailto', 'tel') and _text(target.path): contact = True
        except ValueError:
            continue
    first_title = head.find('title')
    def meta_present(name):
        return any(str(tag.get('name', '')).casefold() == name and _text(tag.get('content')) for tag in head.find_all('meta'))
    return {
        'title_text': metric(int(first_title is not None and bool(all_text.get(id(first_title)))), 1),
        'meta_description': metric(int(meta_present('description')), 1),
        'h1_text': metric(int(any(tag.name == 'h1' and exposed_text.get(id(tag)) for tag in body_tags)), 1),
        'language_declaration': metric(int(_text(root.get('lang'))), 1),
        'viewport_declaration': metric(int(meta_present('viewport')), 1),
        'image_alt_attribute': metric(sum(tag.has_attr('alt') for tag in images), len(images)),
        'link_label_markup': metric(linked, len(anchors)),
        'text_control_label_markup': metric(labeled, len(controls)),
        'contact_scheme_link': metric(int(contact), 1),
    }, None


def report_status(coverage):
    if coverage['inspected_pages'] == 0: return 'unavailable'
    return 'complete' if coverage['inspected_pages'] == coverage['eligible_pages'] else 'partial'


def empty_dom_report():
    return {'schema_version': 1, 'rules_version': RULES_VERSION, 'scope': 'collected_html_dom', 'method': 'dom_rules',
        'status': 'unavailable', 'coverage': {'eligible_pages': 0, 'inspected_pages': 0, 'inconclusive_pages': 0, 'omitted_pages': 0}, 'pages': []}


def validate_dom_report(report):
    try:
        encoded = json.dumps(report, ensure_ascii=False, allow_nan=False)
        _need(len(encoded.encode('utf-8')) <= MAX_REPORT_BYTES)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise AuditValidationError('dom_report_invalid') from None
    _object(report, ('schema_version', 'rules_version', 'scope', 'method', 'status', 'coverage', 'pages'))
    _need(type(report['schema_version']) is int and report['schema_version'] == 1 and report['rules_version'] == RULES_VERSION)
    _need(report['scope'] == 'collected_html_dom' and report['method'] == 'dom_rules')
    _need(isinstance(report['pages'], list) and len(report['pages']) <= 20)
    coverage = report['coverage']
    _object(coverage, ('eligible_pages', 'inspected_pages', 'inconclusive_pages', 'omitted_pages'))
    _need(all(type(value) is int and 0 <= value <= 20 for value in coverage.values()))
    _need(coverage['eligible_pages'] == len(report['pages']) + coverage['omitted_pages'])
    _need(coverage['inspected_pages'] + coverage['inconclusive_pages'] == len(report['pages']))
    _need(report['status'] == report_status(coverage))
    ids = set(); inspected = 0
    for page in report['pages']:
        _object(page, ('id', 'source_url', 'dom_sha256', 'markdown_sha256', 'retrieved_at', 'status', 'reason', 'checks'))
        _need(isinstance(page['id'], str) and re.fullmatch(r'd_[0-9a-f]{64}', page['id']) is not None and page['id'] not in ids)
        ids.add(page['id'])
        _need(isinstance(page['source_url'], str) and public_evidence_url(page['source_url']) == page['source_url'])
        for key in ('markdown_sha256', 'dom_sha256'):
            if key == 'dom_sha256' and page[key] is None: continue
            _need(isinstance(page[key], str) and re.fullmatch(r'[0-9a-f]{64}', page[key]) is not None)
        try:
            stamp = datetime.fromisoformat(page['retrieved_at'].replace('Z', '+00:00'))
            _need(stamp.tzinfo is not None and stamp.utcoffset() == timezone.utc.utcoffset(stamp))
        except (AttributeError, TypeError, ValueError):
            raise AuditValidationError('dom_report_invalid') from None
        if page['status'] == 'inconclusive':
            _need(isinstance(page['reason'], str) and page['reason'] in DOM_REASONS and page['checks'] == {})
            continue
        _need(page['status'] == 'observed' and page['reason'] is None and page['dom_sha256'] is not None)
        inspected += 1
        _object(page['checks'], RULE_IDS)
        for rule, result in page['checks'].items():
            _object(result, ('outcome', 'matched', 'total'))
            _need(type(result['matched']) is int and type(result['total']) is int and 0 <= result['matched'] <= result['total'] <= 1000000)
            _need(rule not in PRESENCE_RULES or result['total'] == 1)
            _need(result == metric(result['matched'], result['total']))
    _need(inspected == coverage['inspected_pages'])
    return json.loads(encoded)
