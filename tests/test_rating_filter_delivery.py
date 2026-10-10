import contextlib
import json
import os
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from openpyxl import load_workbook

from main import LeadHunterOrchestrator, create_orchestrator
from src.application.container import ApplicationContainer
from src.application.rating_filters import RatingFilteredDiscoveryService
from src.domain.rating_filters import RatingFilterCriteria
from src.domain.feature_licenses import LicenseError
from src.domain.place_references import GooglePlaceReference
from src.domain.provenance import VerifiedLead, FieldProvenance, DataSource
from src.exporter import DataExporter
from src.scraper import LeadScraper
from src.settings import ApplicationSettings
from tests.rating_filter_helpers import RatingFilterFixture
from tests.test_compliant_pipeline import _Crawler, _Auditor
from tests.test_rating_filter_discovery import Transport, make_provider, place, Response


def verified_lead():
    provenance = FieldProvenance(DataSource.OFFICIAL_WEBSITE, 'https://official.example/', datetime.now(timezone.utc))
    return VerifiedLead('Official Clinic', 'dentista', 'https://official.example/',
                        provenance={'business_name': provenance, 'website': provenance})


class RatingFilterDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.fx = RatingFilterFixture(self, features=('discovery.rating_filters', 'export.no_website'))
        self.fx.activate()
        self.destination = self.fx.root / 'output' / 'report.xlsx'
        self.destination.parent.mkdir(); self.destination.write_bytes(b'previous-export')
        self.refs = (GooglePlaceReference('0007'),)

    def orchestrator(self, mode, http=None, auditor=None):
        service = RatingFilteredDiscoveryService(make_provider(http), RatingFilterCriteria(), self.fx.guard)
        return LeadHunterOrchestrator(mode, scraper=LeadScraper(provider=service),
                                      auditor=auditor, result_origin=self.fx.guard)

    def test_denial_precedes_google_auditor_crawler_and_geocoding(self):
        self.fx.clock.set(100)
        with patch.object(ApplicationContainer, 'build_scraper') as google, patch.object(ApplicationContainer, 'build_auditor') as auditor:
            with self.assertRaises(LicenseError):
                create_orchestrator('with_website', ApplicationSettings('test', 'test'),
                                    rating_criteria=RatingFilterCriteria(), rating_guard=self.fx.guard)
            google.assert_not_called(); auditor.assert_not_called()
        with patch('src.settings.ApplicationSettings.from_environment') as loader:
            with self.assertRaisesRegex(ValueError, '^rating_filter_invalid$'):
                create_orchestrator('no_website', rating_criteria='invalid')
            loader.assert_not_called()

    def test_both_modes_preserve_order_and_first_qualifying_keyword_duplicate(self):
        def rows(index, kwargs):
            if kwargs['json']['textQuery'] == 'first':
                bad = place('duplicate'); bad['rating'] = 3.9
                return Response({'places': [bad, place('qualified-no-site')]})
            good = place('duplicate', websiteUri='https://official.example.test')
            return Response({'places': [good, place('qualified-no-site')]})
        with contextlib.redirect_stdout(StringIO()):
            no_site = self.orchestrator('no_website', Transport(hook=rows)).run(45, 9, ['first', 'second'])
        self.assertEqual(tuple(c.external_id for c in no_site), ('qualified-no-site',))
        auditor = _Auditor()
        crawler = _Crawler()
        with patch('main.HybridCrawler', return_value=crawler), patch('main.filter_by_business_age', return_value=True), patch('main.filter_franchise', return_value=False):
            results = self.orchestrator('with_website', Transport(hook=rows), auditor).run(45, 9, ['first', 'second'], max_pages=1)
        self.assertEqual([lead.website for lead in results], ['https://official.example.test/'])
        self.assertEqual(auditor.payload['rating'], 0); self.assertEqual(auditor.payload['review_count'], 0)
        self.assertNotIn('qualified-no-site', repr(auditor.payload))
        self.assertNotIn('rating', results[0].to_export_record())

    def test_derived_exports_recheck_after_serialization_and_fsync(self):
        for kind in ['references', 'website']:
            for change in ['expire', 'revoke', 'interrupt']:
                with self.subTest(kind=kind, change=change):
                    fx = RatingFilterFixture(self, features=('discovery.rating_filters', 'export.no_website')); fx.activate()
                    def mutate(_):
                        if change == 'expire': fx.clock.set(100)
                        elif change == 'revoke': fx.licenses.revoke_license(fx.scope, fx.claims.license_id)
                        else: raise KeyboardInterrupt()
                    with patch('os.fsync', side_effect=mutate):
                        with self.assertRaises(KeyboardInterrupt if change == 'interrupt' else LicenseError):
                            if kind == 'references': fx.service().save(self.refs, self.destination, origin=fx.guard)
                            else: DataExporter.export_to_excel([verified_lead()], mode='with_website', filename=str(self.destination), origin=fx.guard)
                    self.assertEqual(self.destination.read_bytes(), b'previous-export')
                    self.assertEqual(list(self.destination.parent.glob('.*-export-*')), [])

    def test_filter_and_reference_export_permissions_are_independent(self):
        for features in [('discovery.rating_filters',), ('export.no_website',)]:
            with self.subTest(features=features):
                fx = RatingFilterFixture(self, features=features); fx.activate()
                with self.assertRaises(LicenseError) as caught:
                    fx.service().save(self.refs, self.destination, origin=fx.guard)
                self.assertEqual(caught.exception.code, 'feature_not_granted')
                self.assertEqual(self.destination.read_bytes(), b'previous-export')
        data = self.fx.service().export_bytes(self.refs, origin=self.fx.guard)
        self.assertEqual([c.value for c in load_workbook(BytesIO(data)).active[1]], ['Place ID', 'Link Google Maps'])

    def test_expiry_inside_workbook_serialization_prevents_bytes_delivery(self):
        for kind in ['references', 'website']:
            with self.subTest(kind=kind):
                fx = RatingFilterFixture(self, features=('discovery.rating_filters', 'export.no_website')); fx.activate()
                original_save = __import__('openpyxl').Workbook.save
                def serialize(workbook, destination):
                    original_save(workbook, destination); fx.clock.set(100)
                with patch('openpyxl.workbook.workbook.Workbook.save', new=serialize):
                    with self.assertRaisesRegex(LicenseError, '^license_expired$'):
                        if kind == 'references': fx.service().export_bytes(self.refs, origin=fx.guard)
                        else: DataExporter.export_bytes([verified_lead()], origin=fx.guard)

    def test_filtered_failure_clears_results_and_never_emits_partial_leads(self):
        auditor = _Auditor()
        original = auditor.audit_website
        def expire(**payload):
            result = original(**payload); self.fx.clock.set(100); return result
        auditor.audit_website = expire
        engine = self.orchestrator('with_website', Transport([place(websiteUri='https://official.example.test')]), auditor)
        output = StringIO()
        with contextlib.redirect_stdout(output), patch('main.HybridCrawler', return_value=_Crawler()), patch('main.filter_by_business_age', return_value=True), patch('main.filter_franchise', return_value=False):
            with self.assertRaises(LicenseError): engine.run_with_website(45, 9, ['dentista'])
        self.assertEqual(engine.all_leads, {}); self.assertEqual(engine.transient_results, [])
        self.assertNotIn('official.example', output.getvalue())

    def test_error_payload_is_redacted_and_provider_metrics_never_enter_zip(self):
        def failing(**payload): raise RuntimeError('provider-secret-sentinel')
        auditor = _Auditor(); auditor.audit_website = failing
        output = StringIO()
        with contextlib.redirect_stdout(output), patch('main.HybridCrawler', return_value=_Crawler()), patch('main.filter_by_business_age', return_value=True), patch('main.filter_franchise', return_value=False):
            self.orchestrator('with_website', Transport([place(websiteUri='https://official.example.test')]), auditor).run(45, 9, ['dentista'])
        self.assertNotIn('provider-secret-sentinel', output.getvalue())
        for data in [self.fx.service().export_bytes(self.refs, origin=self.fx.guard),
                     DataExporter.export_bytes([verified_lead()], origin=self.fx.guard)]:
            with ZipFile(BytesIO(data)) as archive:
                payload = b''.join(archive.read(name) for name in archive.namelist())
            for forbidden in [b'userRatingCount', b'provider-secret-sentinel', b'rating']:
                self.assertNotIn(forbidden, payload)

    def test_write_failure_is_redacted_and_preserves_old_destination(self):
        with patch('src.exporter.os.replace', side_effect=OSError('provider-secret-sentinel')):
            with self.assertRaisesRegex(OSError, '^website_export_write_failed$'):
                DataExporter.export_to_excel([verified_lead()], mode='with_website', filename=str(self.destination), origin=self.fx.guard)
        self.assertEqual(self.destination.read_bytes(), b'previous-export')
        self.assertEqual(list(self.destination.parent.glob('.website-export-*')), [])

    def test_base_needs_no_license_configuration_and_guarded_factory_injects_service(self):
        container = ApplicationContainer(ApplicationSettings('test'))
        with patch.object(ApplicationContainer, 'build_local_license_service', side_effect=AssertionError('base must not load licenses')):
            self.assertIsInstance(container.build_scraper().provider, __import__('src.providers.discovery.google_places', fromlist=['GooglePlacesDiscoveryProvider']).GooglePlacesDiscoveryProvider)
        scraper = container.build_scraper(rating_criteria=RatingFilterCriteria(), rating_guard=self.fx.guard)
        self.assertIsInstance(scraper.provider, RatingFilteredDiscoveryService)
