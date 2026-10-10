import pickle
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from uuid import uuid4
from unittest.mock import Mock

from src.application.rating_filters import RatingFilterGuard
from src.domain.rating_filters import RatingFilterCriteria
from src.domain.feature_licenses import LicenseError
from tests.license_helpers import signed_test_license
from tests.rating_filter_helpers import RatingFilterFixture


class RatingFilterCriteriaTests(unittest.TestCase):
    def setUp(self):
        self.fx = RatingFilterFixture(self)

    def test_defaults_and_exact_types(self):
        self.assertEqual(RatingFilterCriteria(), RatingFilterCriteria(3.9, 100))
        self.assertIs(type(RatingFilterCriteria(0, 1).min_rating), float)
        self.assertEqual(RatingFilterCriteria(5, 2147483647).max_reviews, 2147483647)
        with self.assertRaises(FrozenInstanceError):
            RatingFilterCriteria().max_reviews = 10

    def test_invalid_input_never_creates_dependencies(self):
        dependency_factory = Mock()
        for value in [True, False, '3.9', None, float('nan'), float('inf'),
                      -float('inf'), -0.1, 5.1, 10**1000]:
            with self.subTest(rating=type(value).__name__):
                with self.assertRaisesRegex(ValueError, '^rating_filter_invalid$'):
                    dependency_factory(RatingFilterCriteria(value, 100))
        for value in [True, False, '100', None, 1.0, 0, -1, 2147483648]:
            with self.subTest(count=value):
                with self.assertRaisesRegex(ValueError, '^rating_filter_invalid$'):
                    dependency_factory(RatingFilterCriteria(3.9, value))
        dependency_factory.assert_not_called()

    def test_guard_rechecks_real_license_and_is_not_serializable(self):
        self.fx.activate()
        factory = Mock(side_effect=lambda: self.fx.context)
        guard = RatingFilterGuard(self.fx.access, factory)
        guard.require_execute(); guard.require_view()
        self.assertEqual(factory.call_count, 2)
        self.fx.clock.set(self.fx.claims.expires_at)
        with self.assertRaises(LicenseError) as caught:
            guard.require_view()
        self.assertEqual(caught.exception.code, 'license_expired')
        with self.assertRaises(TypeError):
            pickle.dumps(guard)
        self.assertNotIn('test-owner', repr(guard))
        self.assertNotIn('token', repr(guard))

    def test_guard_observes_current_principal(self):
        self.fx.activate()
        self.fx.guard.require_execute()
        self.fx.context = replace(self.fx.context, principal_active=False)
        with self.assertRaises(LicenseError) as caught:
            self.fx.guard.require_view()
        self.assertEqual(caught.exception.code, 'feature_role_denied')

    def test_real_denials_are_not_replaced_by_boolean_access(self):
        for change, code in [('missing', 'license_missing'), ('ungranted', 'feature_not_granted'),
                             ('tampered', 'license_invalid'), ('revoked', 'license_revoked'),
                             ('other_installation', 'license_subject_mismatch')]:
            with self.subTest(change=change):
                fx = RatingFilterFixture(self)
                if change != 'missing':
                    claims = replace(fx.claims, features=('export.no_website',)) if change == 'ungranted' else fx.claims
                    fx.activate(claims)
                if change == 'tampered':
                    # Valid signed token at import, invalid signature when used.
                    state_path = fx.root / 'state' / 'state.json'
                    state = json.loads(state_path.read_text())
                    state['grant']['token'] = 'tampered.test.token'
                    state_path.write_text(json.dumps(state))
                elif change == 'revoked':
                    fx.licenses.revoke_license(fx.scope, fx.claims.license_id)
                elif change == 'other_installation':
                    identity = uuid4()
                    fx.context = replace(fx.context, scope=replace(fx.scope, installation_id=identity, subject_id=identity))
                with self.assertRaises(LicenseError) as caught:
                    fx.guard.require_execute()
                self.assertEqual(caught.exception.code, code)
