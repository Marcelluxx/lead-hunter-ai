import unittest
from dataclasses import asdict, FrozenInstanceError, replace
from datetime import datetime, timezone
from itertools import repeat

from src.domain.discovery import ProviderAttribution, TransientCandidate
from src.domain.place_references import (
    GooglePlaceReference, ReferenceExportError, normalize_references,
    project_google_place_references,
)


class PlaceReferenceTests(unittest.TestCase):
    def setUp(self):
        attribution = ProviderAttribution('google_places', 'discard-name', 'https://example.test/terms',
                                          'https://example.test/privacy')
        self.candidate = TransientCandidate('google_places', 'ChIJ_1', 'discard-business', None,
                                            datetime.now(timezone.utc), attribution)

    def test_projection_retains_only_google_without_site(self):
        candidates = [self.candidate, replace(self.candidate, website_url='https://site.test'),
                      replace(self.candidate, provider='other'), replace(self.candidate, website_url='')]
        self.assertEqual(project_google_place_references(candidates), (GooglePlaceReference('ChIJ_1'),))
        self.assertEqual(asdict(GooglePlaceReference('ChIJ_1')), {'place_id': 'ChIJ_1'})
        self.assertEqual(project_google_place_references(candidates[1:]), ())

    def test_reference_is_immutable(self):
        reference = GooglePlaceReference('A')
        with self.assertRaises(FrozenInstanceError):
            reference.place_id = 'B'
        with self.assertRaises((FrozenInstanceError, AttributeError, TypeError)):
            reference.display_name = 'forbidden'

    def test_order_case_numeric_and_max_length(self):
        refs = map(GooglePlaceReference, ['0007', 'Ab', 'ab', '0007', 'A' * 500])
        self.assertEqual([r.place_id for r in normalize_references(refs)], ['0007', 'Ab', 'ab', 'A' * 500])

    def test_invalid_id_grammar(self):
        for value in [None, 7, True, '', ' A', '=1+1', '+1', '@x', '-x', 'é', 'A\n', 'A' * 501,
                      'A\x00', 'A/B', 'A?x', 'A B']:
            with self.subTest(value=value), self.assertRaises(ReferenceExportError) as caught:
                GooglePlaceReference(value)
            self.assertEqual(str(caught.exception), 'reference_export_invalid')

    def test_limit_counts_duplicates_and_bounds_iterator(self):
        self.assertEqual(len(normalize_references(repeat(GooglePlaceReference('A'), 10000))), 1)
        consumed = []
        def infinite():
            while True:
                consumed.append(1)
                yield GooglePlaceReference('A')
        with self.assertRaises(ReferenceExportError) as caught:
            normalize_references(infinite())
        self.assertEqual(caught.exception.code, 'reference_export_limit')
        self.assertEqual(len(consumed), 10001)

    def test_mixed_tail_and_empty_are_rejected(self):
        for records, code in [([], 'reference_export_empty'),
                              ([GooglePlaceReference('A'), {'place_id': 'B'}], 'reference_export_invalid'),
                              ([self.candidate], 'reference_export_invalid'), (None, 'reference_export_invalid')]:
            with self.subTest(code=code), self.assertRaises(ReferenceExportError) as caught:
                normalize_references(records)
            self.assertEqual(caught.exception.code, code)

    def test_forged_invalid_reference_is_revalidated(self):
        reference = object.__new__(GooglePlaceReference)
        object.__setattr__(reference, 'place_id', '=1')
        with self.assertRaises(ReferenceExportError) as caught:
            normalize_references([reference])
        self.assertEqual(caught.exception.code, 'reference_export_invalid')

    def test_projection_rejects_raw_payload(self):
        with self.assertRaises(ReferenceExportError) as caught:
            project_google_place_references([{'id': 'A'}])
        self.assertEqual(caught.exception.code, 'reference_export_invalid')
