"""Product availability is independent of signed entitlements."""
from src.domain.feature_licenses import FeatureDefinition, LicenseError
from src.domain.identity import Permission


class FeatureCatalog:
    def all(self) -> tuple[FeatureDefinition, ...]:
        return (
            FeatureDefinition("export.no_website", "Export senza sito", "planned",
                              (Permission.EXPORT_RESULTS,), (Permission.EXPORT_RESULTS,)),
            FeatureDefinition("discovery.rating_filters", "Filtri rating e recensioni", "planned",
                              (Permission.START_JOB,), (Permission.VIEW_RESULTS,)),
            FeatureDefinition("diagnostics.full", "Diagnostica completa", "planned",
                              (Permission.START_JOB,), (Permission.VIEW_AUDIT_LOG,), True, True),
        )

    def get(self, feature_id: str) -> FeatureDefinition:
        for feature in self.all():
            if feature.feature_id == feature_id:
                return feature
        raise LicenseError("feature_unavailable")
