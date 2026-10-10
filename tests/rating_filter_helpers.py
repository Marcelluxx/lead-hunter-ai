"""Real signed ephemeral grants; only module availability is overridden."""
from dataclasses import replace
from unittest.mock import patch

from src.application.rating_filters import RatingFilterGuard
from src.domain.feature_licenses import FeatureContext
from src.domain.identity import Permission
from src.licensing.catalog import FeatureCatalog
from tests.reference_export_helpers import ReferenceExportFixture


class AvailableRatingCatalog(FeatureCatalog):
    def all(self):
        return tuple(replace(item, module_status='available')
                     if item.feature_id == 'discovery.rating_filters' else item
                     for item in super().all())


class RatingFilterFixture(ReferenceExportFixture):
    def __init__(self, testcase, *, features=('discovery.rating_filters',), available=True):
        if available:
            catalog = patch('src.licensing.catalog.FeatureCatalog', AvailableRatingCatalog)
            catalog.start(); testcase.addCleanup(catalog.stop)
        super().__init__(testcase, available=False)
        self.claims = replace(self.claims, features=features)
        self.context = FeatureContext(self.scope, frozenset(Permission), False, True)
        self.guard = RatingFilterGuard(self.access, lambda: self.context)
