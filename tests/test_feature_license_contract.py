import unittest
from dataclasses import replace
from uuid import UUID

from src.domain.feature_licenses import LicenseError, LicenseScope, SubjectKind
from src.domain.identity import Permission
from src.licensing.catalog import FeatureCatalog
from tests.license_helpers import license_claims, local_scope, managed_scope


class FeatureLicenseContractTests(unittest.TestCase):
    def test_catalog_exposes_completed_rating_filters_and_reference_export(self):
        catalog = FeatureCatalog()
        self.assertEqual({x.feature_id for x in catalog.all()},
                         {'export.no_website', 'discovery.rating_filters', 'diagnostics.full'})
        self.assertEqual(catalog.get('export.no_website').module_status, 'available')
        self.assertEqual(catalog.get('export.no_website').label, 'Export riferimenti senza sito')
        self.assertEqual(catalog.get('discovery.rating_filters').module_status, 'available')
        self.assertEqual(catalog.get('diagnostics.full').module_status, 'available')
        diag = catalog.get('diagnostics.full')
        self.assertEqual(diag.execute_permissions, (Permission.START_JOB,))
        self.assertEqual(diag.view_permissions, (Permission.VIEW_AUDIT_LOG,))
        self.assertTrue(diag.execute_mfa and diag.view_mfa)
        export = catalog.get('export.no_website')
        self.assertEqual(export.execute_permissions, (Permission.EXPORT_RESULTS,))
        self.assertEqual(export.view_permissions, (Permission.EXPORT_RESULTS,))
        filters = catalog.get('discovery.rating_filters')
        self.assertEqual(filters.execute_permissions, (Permission.START_JOB,))
        self.assertEqual(filters.view_permissions, (Permission.VIEW_RESULTS,))
        self.assertFalse(filters.execute_mfa or filters.view_mfa)

    def test_scope_and_claim_types_are_strict(self):
        scope = local_scope()
        for changes in ({'subject_id': UUID(int=2)}, {'workspace_id': UUID(int=3)},
                        {'subject_kind': 'installation'}, {'installation_id': 'bad'}):
            with self.subTest(changes=changes), self.assertRaises(LicenseError):
                replace(scope, **changes)
        with self.assertRaises(LicenseError):
            replace(managed_scope(), workspace_id=None)
        claims = license_claims()
        for changes in ({'features': ()}, {'features': ('*',)},
                        {'features': ('diagnostics.full', 'diagnostics.full')},
                        {'version': True}, {'issued_at': True}, {'not_before': 1.1},
                        {'expires_at': '100'}, {'expires_at': 253402300800},
                        {'issued_at': -1}, {'issued_at': 11, 'not_before': 10},
                        {'not_before': 100}, {'features': ['diagnostics.full']}):
            with self.subTest(changes=changes), self.assertRaises(LicenseError):
                replace(claims, **changes)
