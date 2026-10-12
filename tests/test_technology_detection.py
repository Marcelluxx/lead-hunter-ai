import unittest


class TechnologyDetectionTests(unittest.TestCase):
    def test_generator_and_asset_fingerprints_have_public_signals_without_version_claims(self):
        from src.domain.technology import detect_technologies
        cases = [('WordPress', '<meta name="generator" content="WordPress 6.8">'),
            ('Drupal', '<meta name="generator" content="Drupal 10">'),
            ('Joomla', '<meta name="generator" content="Joomla!">'),
            ('Shopify', '<script src="https://cdn.shopify.com/s/assets/theme.js"></script>'),
            ('Wix', '<script src="https://static.parastorage.com/services/wix-thunderbolt/main.js"></script>'),
            ('Squarespace', '<script src="https://static1.squarespace.com/static/site.js"></script>'),
            ('Next.js', '<script src="/_next/static/chunks/main.js"></script>'),
            ('Nuxt', '<script src="/_nuxt/app.js"></script>')]
        for name, html in cases:
            with self.subTest(name=name):
                matches = detect_technologies(html)
                self.assertEqual([x.name for x in matches], [name])
                self.assertEqual(matches[0].rules_version, '1')
                self.assertTrue(matches[0].signals)
                self.assertGreater(matches[0].confidence, 0)
                self.assertNotIn('6.8', repr(matches))
                self.assertNotIn('<', repr(matches))

    def test_names_in_articles_comments_templates_and_query_parameters_are_not_fingerprints(self):
        from src.domain.technology import detect_technologies
        for html in ['<p>WordPress Drupal Shopify Wix Squarespace Next.js Nuxt</p>',
            '<!-- <meta name="generator" content="WordPress"> -->',
            '<template><script src="/_next/static/main.js"></script></template>',
            '<script src="/analytics.js?site=cdn.shopify.com&path=/_nuxt/"></script>',
            '<script src="https://cdn.shopify.com.example.org/store.js"></script>', '', None]:
            with self.subTest(html=html):
                self.assertEqual(detect_technologies(html), ())

    def test_duplicate_assets_are_deduplicated_and_secrets_never_enter_signals(self):
        from src.domain.technology import detect_technologies
        html = '<script src="/_next/static/main.js?token=SECRET_SENTINEL"></script>' * 100
        matches = detect_technologies(html)
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[0].signals), 1)
        self.assertNotIn('SECRET_SENTINEL', repr(matches))
        self.assertNotIn('main.js', repr(matches))

