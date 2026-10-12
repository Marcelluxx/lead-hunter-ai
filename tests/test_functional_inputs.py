import contextlib
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from main import main
from src.settings import ApplicationSettings
from src.filters import clean_and_translate_categories, extract_address_details


class FunctionalInputTests(unittest.TestCase):
    def setUp(self):
        self.output = StringIO()
        redirect = contextlib.redirect_stdout(self.output); redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def test_zero_coordinates_are_valid_and_reach_the_existing_search(self):
        run = Mock(return_value=[])
        with patch('main.ApplicationSettings.from_environment', return_value=ApplicationSettings()), \
                patch('main.create_orchestrator', return_value=SimpleNamespace(run=run)):
            self.assertEqual(main(['--lat', '0', '--lng', '0', '--keywords', 'studio', '--out', 'fixture.xlsx']), 0)
        run.assert_called_once_with(0.0, 0.0, ['studio'])

    def test_invalid_search_input_precedes_environment_or_orchestrator(self):
        cases = [['--lat', lat, '--lng', lng, '--keywords', 'studio'] for lat, lng in
            [('nan', '9'), ('inf', '9'), ('91', '9'), ('-91', '9'), ('0', '181'), ('0', 'nan')]]
        cases += [[], ['--lat', '0', '--lng', '0', '--keywords', ' '],
            ['--lat', '0', '--lng', '0', '--keywords', 'studio', '--min-age', '0'],
            ['--lat', '0', '--lng', '0', '--keywords', 'studio', '--max-pages', '21']]
        for args in cases:
            with self.subTest(args=args), patch('main.ApplicationSettings.from_environment') as settings, \
                    patch('main.create_orchestrator') as orchestrator:
                self.assertEqual(main(args), 2)
                settings.assert_not_called(); orchestrator.assert_not_called()

    def test_invalid_test_url_precedes_environment_prompt_and_archive_cleanup(self):
        for full in [False, True]:
            for url in ['not-a-url', 'https://user:SECRET_SENTINEL@site.test/', 'http://localhost/', 'https://[broken',
                    'https://exa mple.com/', 'https://example.com:0/']:
                args = ['--test-url', url] + (['--full-diagnostics'] if full else [])
                with self.subTest(full=full, url=url), patch('main.ApplicationSettings.from_environment') as settings, \
                        patch('main.ApplicationContainer') as container, patch('main.HybridCrawler') as crawler, \
                        patch('src.application.diagnostics.purge_diagnostic_archives') as cleanup:
                    self.assertEqual(main(args), 2)
                    settings.assert_not_called(); container.assert_not_called(); crawler.assert_not_called(); cleanup.assert_not_called()
        self.assertNotIn('SECRET_SENTINEL', self.output.getvalue())

    def test_examples_exit_without_settings_or_search(self):
        with patch('main.ApplicationSettings.from_environment') as settings, patch('main.create_orchestrator') as orchestrator:
            self.assertEqual(main(['--examples']), 0)
            settings.assert_not_called(); orchestrator.assert_not_called()

    def test_categories_tolerate_missing_mixed_and_repeated_types(self):
        self.assertEqual(clean_and_translate_categories([None, ' dentist ', 'DENTIST', 42]), 'Dentista')
        self.assertEqual(clean_and_translate_categories(None, 'studio'), 'Studio')
        self.assertEqual(clean_and_translate_categories(['cafe', 'coffee_shop', 'restaurant', 'dentist']), 'Bar, Ristorante')
        self.assertEqual(clean_and_translate_categories([False, None], None), 'N/A')

    def test_locality_is_not_invented_and_international_names_keep_their_case(self):
        for lead in [None, {}, {'search_keyword': 'Dentista'}, {'addressComponents': None, 'formattedAddress': None}]:
            with self.subTest(lead=lead):
                self.assertEqual(extract_address_details(lead), ('N/A', 'N/A'))
        for city in ['LA', 'RIO DE JANEIRO', 'São Paulo']:
            lead = {'addressComponents': [None, {'types': ['route'], 'longText': 'Avenida Aurora'},
                {'types': ['street_number'], 'longText': '10'}, {'types': ['locality'], 'longText': city}]}
            self.assertEqual(extract_address_details(lead), ('Avenida Aurora, 10', city))
        self.assertEqual(extract_address_details({'formattedAddress': 'Main Street, 10, 90001 LA, USA'}), ('Main Street, 10', 'LA'))

