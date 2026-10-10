"""Current authorization and trusted operational origin for filtered discovery."""
from collections.abc import Callable

from src.application.feature_access import FeatureAccessService
from src.domain.feature_licenses import FeatureAction, FeatureContext


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
