"""Composition root for runtime provider dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..auditor import LeadAuditor
from ..config import FIELD_MASK
from ..prompting import AuditPromptProvider
from ..scraper import LeadScraper
from ..settings import ApplicationSettings
from ..domain.rating_filters import RatingFilterCriteria
from .rating_filters import RatingFilterGuard, RatingFilteredDiscoveryService


@dataclass(frozen=True)
class ApplicationContainer:
    settings: ApplicationSettings
    prompt_provider: Optional[AuditPromptProvider] = None

    @classmethod
    def from_environment(cls) -> "ApplicationContainer":
        return cls(ApplicationSettings.from_environment())

    def build_scraper(self, *, rating_criteria: RatingFilterCriteria | None = None,
                      rating_guard: RatingFilterGuard | None = None) -> LeadScraper:
        if ((rating_criteria is None) != (rating_guard is None) or
            (rating_criteria is not None and (not isinstance(rating_criteria, RatingFilterCriteria)
                                             or not isinstance(rating_guard, RatingFilterGuard)))):
            raise ValueError('rating_filter_invalid')
        if rating_guard is not None:
            rating_guard.require_execute()
        self.settings.require_google()
        scraper = LeadScraper(
            api_key=self.settings.google_api_key,
            places_url=self.settings.google_places_url,
            geocoding_url=self.settings.google_geocoding_url,
            field_mask=FIELD_MASK,
        )
        if rating_guard is not None:
            scraper.provider = RatingFilteredDiscoveryService(scraper.provider, rating_criteria, rating_guard)
        return scraper

    def build_auditor(self) -> LeadAuditor:
        self.settings.require_openrouter()
        return LeadAuditor(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
            model=self.settings.llm_model,
            model_free=self.settings.llm_model_free,
            prompt_provider=self.prompt_provider,
        )
    def build_local_license_service(self):
        from .feature_licenses import LicenseService
        from .feature_access import FeatureAccessService
        from .license_clock import GuardedClock, SystemClock
        from ..domain.feature_licenses import LicenseScope, SubjectKind
        from ..infrastructure.license_local_store import LocalLicenseStore
        from ..licensing.catalog import FeatureCatalog
        from ..licensing.settings import LicenseSettings
        from ..licensing.verification import LicenseVerifier
        config = LicenseSettings.from_environment()
        store = LocalLicenseStore(config.local_state_dir)
        identity = store.installation_id()
        scope = LicenseScope(identity, SubjectKind.INSTALLATION, identity)
        catalog = FeatureCatalog()
        licenses = LicenseService(store, LicenseVerifier(config.load_trusted_keys(), catalog),
                                  GuardedClock(SystemClock(), store))
        return scope, licenses, FeatureAccessService(licenses, catalog)

    def build_local_reference_export_service(self) -> "ReferenceExportService":
        from .reference_exports import ReferenceExportService
        from ..domain.feature_licenses import FeatureContext
        from ..domain.identity import Permission
        scope, _, access = self.build_local_license_service()
        return ReferenceExportService(access, lambda: FeatureContext(
            scope, frozenset(Permission), False, True))

    def build_local_rating_filter_guard(self) -> RatingFilterGuard:
        from ..domain.feature_licenses import FeatureContext
        from ..domain.identity import Permission
        scope, _, access = self.build_local_license_service()
        return RatingFilterGuard(access, lambda: FeatureContext(scope, frozenset(Permission), False, True))
