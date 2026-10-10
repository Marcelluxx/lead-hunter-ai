"""Current authorization and trusted operational origin for filtered discovery."""
from __future__ import annotations
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.application.feature_access import FeatureAccessService
from src.domain.feature_licenses import FeatureAction, FeatureContext
from src.domain.discovery import DiscoveryQuery, DiscoveryBatch
from src.domain.rating_filters import RatingFilterCriteria

if TYPE_CHECKING:
    from src.providers.discovery.google_places import GooglePlacesDiscoveryProvider


class RatingFilterGuard:
    def __init__(self, access: FeatureAccessService, context_factory: Callable[[], FeatureContext]):
        self._access = access
        self._context_factory = context_factory

    def require_execute(self) -> None:
        self._access.require(self._context_factory(), 'discovery.rating_filters',
                             action=FeatureAction.EXECUTE)

    def require_view(self) -> None:
        self._access.require(self._context_factory(), 'discovery.rating_filters', action=FeatureAction.VIEW)

    def __reduce_ex__(self, protocol):
        raise TypeError('runtime_guard_not_serializable')

    def __repr__(self) -> str:
        return '<RatingFilterGuard>'


class RatingFilteredDiscoveryService:
    def __init__(self, provider: GooglePlacesDiscoveryProvider, criteria: RatingFilterCriteria,
                 guard: RatingFilterGuard):
        if not isinstance(criteria, RatingFilterCriteria) or not isinstance(guard, RatingFilterGuard):
            raise ValueError('rating_filter_invalid')
        self._provider, self._criteria, self._guard = provider, criteria, guard
        self.attribution, self.retention = provider.attribution, provider.retention

    def discover(self, query: DiscoveryQuery, *,
                 on_progress: Callable[[int, int], None] | None = None) -> DiscoveryBatch:
        self._guard.require_execute()
        batch = self._provider._discover_filtered(query, criteria=self._criteria, guard=self._guard,
                                                 on_progress=on_progress)
        self._guard.require_view()
        return batch
