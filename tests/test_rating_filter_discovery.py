import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import requests
from sqlalchemy import delete, update

from src.application.rating_filters import RatingFilterGuard, RatingFilteredDiscoveryService
from src.application.feature_access import FeatureAccessService, server_feature_context
from src.application.feature_licenses import LicenseService
from src.domain.discovery import DiscoveryQuery
from src.domain.feature_licenses import LicenseError
from src.domain.rating_filters import RatingFilterCriteria
from src.infrastructure.license_repository import SqlLicenseRepository
from src.infrastructure.models import UserModel, WorkspaceModel, WorkspaceMembershipModel
from src.providers.discovery.google_places import GooglePlacesDiscoveryProvider, DiscoveryProviderError
from tests.license_helpers import license_claims, seed_license_subject, signed_test_license
from tests.platform_helpers import platform_fixture
from tests.rating_filter_helpers import RatingFilterFixture, AvailableRatingCatalog

BASE_MASK = 'places.id,places.displayName,places.websiteUri,places.attributions'
QUERY = DiscoveryQuery('dentista', 45, 9)


def place(identifier='valid', **fields):
    return dict(id=identifier, displayName={'text': identifier}, rating=4.5, userRatingCount=10, **fields)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class Transport:
    def __init__(self, places=None, hook=None):
        self.places = places if places is not None else [place()]
        self.hook = hook
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(kwargs)
        if self.hook:
            result = self.hook(len(self.calls), kwargs)
            if result is not None:
                return result
        return Response({'places': self.places})


def make_provider(http=None, **kwargs):
    return GooglePlacesDiscoveryProvider(api_key='test-only', places_url='https://places.test/search',
        http_client=http or Transport(), grid_size=kwargs.pop('grid_size', 1),
        inter_request_delay_s=0, field_mask=kwargs.pop('field_mask', BASE_MASK), **kwargs)


class RatingFilterDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.fx = RatingFilterFixture(self); self.fx.activate()

    def service(self, http=None, criteria=None, **kwargs):
        return RatingFilteredDiscoveryService(make_provider(http, **kwargs),
            criteria or RatingFilterCriteria(), self.fx.guard)

    def test_strict_boundaries_and_missing_metrics(self):
        rows = []
        for identifier, rating, count in [('at-threshold', 3.9, 10), ('above-threshold', 4, 1),
            ('at-max-count', 5, 100), ('zero', 4, 0), ('over-max', 4, 101)]:
            row = place(identifier); row.update(rating=rating, userRatingCount=count); rows.append(row)
        batch = self.service(Transport(rows)).discover(QUERY)
        self.assertEqual(tuple(c.external_id for c in batch.candidates), ('above-threshold', 'at-max-count'))
        for key, values in [('rating', [None, True, False, '4.5', float('nan'), float('inf'), -1, 6]),
                            ('userRatingCount', [None, True, False, '10', 10.0, 1.5, -1, 0, 2147483648])]:
            for value in values + ['missing']:
                with self.subTest(key=key, value=value):
                    bad = place('bad')
                    if value == 'missing': bad.pop(key)
                    else: bad[key] = value
                    batch = self.service(Transport([bad, None, 'bad', place()])).discover(QUERY)
                    self.assertEqual(tuple(c.external_id for c in batch.candidates), ('valid',))
        self.assertEqual(len(self.service(criteria=RatingFilterCriteria(5)).discover(QUERY).candidates), 0)
        self.assertEqual(len(self.service(criteria=RatingFilterCriteria(0)).discover(QUERY).candidates), 1)
        self.assertNotIn('rating', vars(batch.candidates[0]))
        self.assertNotIn('userRatingCount', vars(batch.candidates[0]))

    def test_request_masks_do_not_leak_after_filtered_search_or_concurrently(self):
        http = Transport(); provider = make_provider(http)
        service = RatingFilteredDiscoveryService(provider, RatingFilterCriteria(), self.fx.guard)
        service.discover(QUERY); provider.discover(QUERY); service.discover(QUERY)
        for index in [0, 2]:
            self.assertEqual(set(http.calls[index]['headers']['X-Goog-FieldMask'].split(',')) - set(BASE_MASK.split(',')),
                             {'places.rating', 'places.userRatingCount'})
            self.assertNotIn('minRating', http.calls[index]['json'])
        self.assertEqual(http.calls[1]['headers']['X-Goog-FieldMask'], BASE_MASK)
        self.assertEqual(provider.headers['X-Goog-FieldMask'], BASE_MASK)
        provider.headers['X-Goog-FieldMask'] = '*'
        provider.discover(QUERY)
        self.assertEqual(http.calls[-1]['headers']['X-Goog-FieldMask'], BASE_MASK)
        barrier = Barrier(2)
        http.hook = lambda *_: barrier.wait(timeout=10) and None
        # Return None explicitly, regardless of barrier index.
        def synchronized(*_): barrier.wait(timeout=10)
        http.hook = synchronized
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(provider.discover, QUERY), pool.submit(service.discover, QUERY)]
            for future in futures: self.assertEqual(len(future.result().candidates), 1)
        self.assertEqual(sorted(c['headers']['X-Goog-FieldMask'] for c in http.calls[-2:]),
                         sorted([BASE_MASK, BASE_MASK + ',places.rating,places.userRatingCount']))

    def test_base_constructor_rejects_protected_or_unbounded_mask(self):
        for mask in ['*', 'places.id,places.rating', 'places.userRatingCount',
                     'places.reviews', 'places.formattedAddress', 'places.nationalPhoneNumber', '']:
            with self.subTest(mask=mask), self.assertRaisesRegex(ValueError, '^provider_field_mask_invalid$'):
                make_provider(field_mask=mask)
        self.assertEqual(make_provider(field_mask='places.id').headers['X-Goog-FieldMask'], 'places.id')

    def test_first_qualifying_duplicate_wins(self):
        bad = place('duplicate'); bad['rating'] = 3.9
        good = place('duplicate'); good['displayName'] = {'text': 'qualifying-occurrence'}
        later = place('duplicate'); later['displayName'] = {'text': 'later-occurrence'}
        batch = self.service(Transport([bad, good, place('second'), later])).discover(QUERY)
        self.assertEqual(tuple(c.external_id for c in batch.candidates), ('duplicate', 'second'))
        self.assertEqual(batch.candidates[0].display_name, 'qualifying-occurrence')

    def test_expiry_between_cells_retries_and_progress_callback(self):
        for scenario in ['cell', 'retry', 'first_progress', 'second_progress', 'inflight', 'revoke']:
            with self.subTest(scenario=scenario):
                fx = RatingFilterFixture(self); fx.activate()
                def invalidate():
                    if scenario == 'revoke': fx.licenses.revoke_license(fx.scope, fx.claims.license_id)
                    else: fx.clock.set(100)
                def hook(index, kwargs):
                    if scenario not in ['first_progress', 'second_progress']:
                        invalidate()
                    if scenario == 'retry': raise requests.Timeout('provider-secret-sentinel')
                http = Transport(hook=hook)
                service = RatingFilteredDiscoveryService(make_provider(http, grid_size=3 if scenario in ['cell', 'second_progress'] else 1),
                                                         RatingFilterCriteria(), fx.guard)
                def progress(current, total):
                    if scenario == 'first_progress' or (scenario == 'second_progress' and current == 2): invalidate()
                with self.assertRaises(LicenseError) as caught: service.discover(QUERY, on_progress=progress)
                self.assertEqual(caught.exception.code, 'license_revoked' if scenario == 'revoke' else 'license_expired')
                self.assertEqual(len(http.calls), 0 if scenario == 'first_progress' else 1)

    def test_global_invalid_responses_and_bounded_retries_remain_safe(self):
        for payload in [None, [], {'places': None}, {'places': 'secret'}]:
            http = Transport(hook=lambda *_: Response(payload))
            with self.assertRaisesRegex(DiscoveryProviderError, '^provider_invalid_response$'):
                self.service(http).discover(QUERY)
        for error in [requests.Timeout('secret'), requests.ConnectionError('secret')]:
            def fail(*_): raise error
            http = Transport(hook=fail)
            with self.assertRaises(DiscoveryProviderError): self.service(http).discover(QUERY)
            self.assertEqual(len(http.calls), 2)
        for status in [429, 500, 400]:
            def fail(index, kwargs):
                if index == 1:
                    raise requests.HTTPError('secret', response=SimpleNamespace(status_code=status))
            http = Transport(hook=fail)
            if status == 400:
                with self.assertRaisesRegex(DiscoveryProviderError, '^provider_http_error$'): self.service(http).discover(QUERY)
                self.assertEqual(len(http.calls), 1)
            else:
                self.assertEqual(len(self.service(http).discover(QUERY).candidates), 1)
                self.assertEqual(len(http.calls), 2)

    def test_server_context_is_current_per_attempt_and_delivery(self):
        for change in ['viewer_attempt', 'viewer_view', 'remove', 'inactive_user', 'inactive_workspace', 'scope']:
            with self.subTest(change=change):
                db, *_ = platform_fixture(); self.addCleanup(db.engine.dispose)
                scope = seed_license_subject(db)
                claims = license_claims(scope=scope, features=('discovery.rating_filters',))
                with db.session(scope.workspace_id) as session:
                    licenses = LicenseService(SqlLicenseRepository(session, scope.installation_id), self.fx.licenses.verifier, self.fx.clock)
                    licenses.import_license(scope, signed_test_license(claims, self.fx.private))
                with db.session(scope.workspace_id) as session:
                    licenses = LicenseService(SqlLicenseRepository(session, scope.installation_id), self.fx.licenses.verifier, self.fx.clock)
                    auth = SimpleNamespace(user_id=scope.subject_id, mfa_verified=False)
                    guard = RatingFilterGuard(FeatureAccessService(licenses, AvailableRatingCatalog()),
                        lambda: server_feature_context(session, auth=auth, workspace_id=scope.workspace_id,
                                                       installation_id=scope.installation_id))
                    def mutate(index, kwargs):
                        with db.session() as writer:
                            membership = WorkspaceMembershipModel.user_id == scope.subject_id
                            if change.startswith('viewer'):
                                writer.execute(update(WorkspaceMembershipModel).where(membership).values(role='viewer'))
                            elif change == 'remove': writer.execute(delete(WorkspaceMembershipModel).where(membership))
                            elif change == 'inactive_user': writer.execute(update(UserModel).where(UserModel.id == scope.subject_id).values(is_active=False))
                            elif change == 'inactive_workspace': writer.execute(update(WorkspaceModel).where(WorkspaceModel.id == scope.workspace_id).values(is_active=False))
                            else: auth.user_id = uuid4()
                    http = Transport(hook=mutate)
                    service = RatingFilteredDiscoveryService(make_provider(http, grid_size=3 if change == 'viewer_attempt' else 1), RatingFilterCriteria(), guard)
                    if change == 'viewer_view': self.assertEqual(len(service.discover(QUERY).candidates), 1)
                    else:
                        with self.assertRaises(LicenseError): service.discover(QUERY)
                    self.assertEqual(len(http.calls), 1)
