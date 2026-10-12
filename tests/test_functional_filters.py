"""Qualification regressions using local DOM and WHOIS fixtures only."""
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from src.config import ECOMMERCE_INDICATORS
from src.filters import (filter_by_business_age, _check_whois_age, _check_copywriting_age,
    filter_social_media, filter_franchise, extract_domain, filter_ecommerce)

SHOP_DOM = '''<form action="/cart/add"><button>Aggiungi al carrello</button></form>
<script type="application/ld+json">{"@type":"Product","offers":{"@type":"Offer","price":"10"}}</script>'''


class FunctionalFilterTests(unittest.TestCase):
    def test_malformed_dom_urls_do_not_abort_qualification_or_hide_valid_signals(self):
        broken = '<a href="https://[broken">Contatti</a><script src="https://[broken"></script>'
        self.assertFalse(filter_ecommerce(broken, []))
        self.assertTrue(filter_ecommerce(broken + SHOP_DOM, []))
        self.assertTrue(filter_ecommerce(broken + '<a href="/cart">Carrello</a>'
            '<script src="/plugins/woocommerce/cart.js"></script>', []))

    def test_known_recent_domain_is_excluded_unknown_still_allowed_and_old_copy_overrides(self):
        with patch('src.filters.whois.whois', return_value=SimpleNamespace(creation_date=datetime(datetime.now().year, 1, 1))) as lookup:
            self.assertFalse(filter_by_business_age('studio.test', '', 5))
            self.assertTrue(filter_by_business_age('studio.test', '<p>Dal 1999</p>', 5))
            lookup.assert_called_with('studio.test', timeout=10)
        with patch('src.filters.whois.whois', side_effect=TimeoutError('private error')):
            self.assertTrue(filter_by_business_age('studio.test', '', 5))

    def test_whois_multiple_dates_choose_oldest_valid_not_first_and_future_is_unknown(self):
        year = datetime.now().year
        for dates, expected in [([None, 'redacted', datetime(year, 1, 1), datetime(2000, 1, 1)], True),
                                ([datetime(year + 1, 1, 1)], None), ([], None), ('redacted', None)]:
            with self.subTest(dates=dates), patch('src.filters.whois.whois', return_value=SimpleNamespace(creation_date=dates)):
                self.assertIs(_check_whois_age('studio.test', year - 5), expected)

    def test_copywriting_ignores_invisible_dates_and_checks_all_visible_evidence(self):
        year = datetime.now().year
        invisible = '<script>dal 1999</script><style>since 1999</style><!-- dal 1999 --><p hidden>Dal 1999</p>'
        self.assertIsNone(_check_copywriting_age(invisible, year - 5, 5))
        mixed = f'<p>Nato nel {year}. La nostra azienda opera dal 1999.</p>'
        self.assertTrue(_check_copywriting_age(mixed, year - 5, 5))
        self.assertFalse(_check_copywriting_age(f'<p>Fondato nel {year}</p>', year - 5, 5))

    def test_social_only_matches_hostname_or_subdomain(self):
        for value, expected in [('x.com', True), ('m.x.com.', True), ('HTTPS://WWW.X.COM/path', True),
            ('examplex.com', False), ('instagram.com.example.org', False),
            ('https://studio.test/facebook.com?x=x.com', False)]:
            with self.subTest(value=value):
                self.assertEqual(filter_social_media(value, ['x.com', 'instagram.com', 'facebook.com']), expected)

    def test_hostname_extraction_normalizes_without_path_port_or_userinfo(self):
        for value, expected in [('HTTPS://USER:pass@WWW.Example.COM.:443/path?q=x', 'example.com'),
            ('www.example.com/path', 'example.com'), ('https://bücher.example/path', 'xn--bcher-kva.example'),
            ('http://[2001:db8::1]:80/', '2001:db8::1'), ('', ''), ('not a host', '')]:
            with self.subTest(value=value):
                self.assertEqual(extract_domain(value), expected)

    def test_franchise_requires_complete_known_brand_not_substring_or_repeated_generic_names(self):
        for value, expected in [('PAM Milano', True), ('Pampa Studio', False), ('Cooperativa Aurora', False),
            ('McDonald’s Milano', True), ('La Piadineria - Centro', True), ('Studio', False)]:
            with self.subTest(value=value):
                self.assertEqual(filter_franchise(value, ['Studio Uno', 'Studio Due', 'Studio Tre'],
                    ['pam', 'coop', 'mcdonald', 'la piadineria']), expected)

    def test_ecommerce_requires_action_and_independent_commercial_structure(self):
        positives = [SHOP_DOM,
            '<a href="/checkout">Checkout</a><div itemtype="https://schema.org/Product"><meta itemprop="price" content="10"></div>',
            '<button class="add-to-cart">Aggiungi</button><script src="https://cdn.shopify.com/assets/store.js"></script>',
            '<a href="/?add-to-cart=1">Aggiungi</a><span class="woocommerce-Price-amount">20 euro</span>']
        negatives = ['<p>Blog su Stripe e cart</p>', '<p>Confronto Shopify e WooCommerce</p>',
            '<!-- cart checkout shopify -->', '<script>const article="cart checkout"</script>',
            '<p>Acquista una consulenza. Accettiamo Stripe.</p>', '<a href="/blog/checkout">Articolo sul checkout</a>',
            '<script type="application/ld+json">{"@type":"Product","offers":{"price":"10"}}</script>',
            '<button class="add-to-cart">Tutorial</button>']
        for html, expected in [(x, True) for x in positives] + [(x, False) for x in negatives]:
            with self.subTest(html=html):
                self.assertEqual(filter_ecommerce(html, ECOMMERCE_INDICATORS), expected)
        self.assertFalse(filter_ecommerce('<p>cart</p>', ['cart', 'cart']))
