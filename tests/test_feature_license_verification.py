import base64
import json
import unittest
from dataclasses import replace

import jwt
from cryptography.hazmat.primitives import serialization

from src.domain.feature_licenses import LicenseError
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import LicenseVerifier
from tests.license_helpers import (claim_payload, license_claims, local_scope, managed_scope,
                                  signed_test_license, test_key_pair)


class FeatureLicenseVerificationTests(unittest.TestCase):
    def setUp(self):
        self.private, public = test_key_pair()
        self.verifier = LicenseVerifier(TrustedLicenseKeys('test-owner', {'test-key': public}),
                                        FeatureCatalog())
        self.payload = claim_payload(license_claims())

    def token(self, payload=None, headers=None, private=None):
        return jwt.encode(payload if payload is not None else self.payload, private or self.private,
                          algorithm='EdDSA', headers=headers or
                          {'typ': 'LH-FEATURE-LICENSE', 'kid': 'test-key'})

    def reject(self, token, code='license_invalid', scope=None):
        with self.assertRaises(LicenseError) as caught:
            self.verifier.verify(token, scope=scope or local_scope(), now_epoch=10)
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn(token, str(caught.exception))

    def test_validity_has_inclusive_start_exclusive_end(self):
        token = signed_test_license(license_claims(not_before=10), self.private)
        for now, expected in ((9, 'license_not_yet_valid'), (100, 'license_expired')):
            with self.subTest(now=now), self.assertRaises(LicenseError) as caught:
                self.verifier.verify(token, scope=local_scope(), now_epoch=now)
            self.assertEqual(caught.exception.code, expected)
        for now in (10, 99):
            self.assertEqual(self.verifier.verify(token, scope=local_scope(),
                                                  now_epoch=now).expires_at, 100)

    def test_signature_and_trust_are_strict(self):
        token = self.token()
        altered = token.rsplit('.', 1)[0] + '.' + ('A' if token.rsplit('.', 1)[1][0] != 'A' else 'B') + token.rsplit('.', 1)[1][1:]
        cases = [altered, self.token(private=test_key_pair()[0]),
                 jwt.encode(self.payload, '', algorithm='none',
                            headers={'typ': 'LH-FEATURE-LICENSE', 'kid': 'test-key'}),
                 jwt.encode(self.payload, b'x'*32, algorithm='HS256',
                            headers={'typ': 'LH-FEATURE-LICENSE', 'kid': 'test-key'}),
                 'x' * 16385, token + 'é']
        for extra in ({'kid': 'unknown'}, {'jku': 'https://untrusted.test'},
                      {'x5u': 'https://untrusted.test'}, {'typ': 'JWT'}):
            cases.append(self.token(headers={'typ': 'LH-FEATURE-LICENSE', 'kid': 'test-key', **extra}))
        for item in cases:
            with self.subTest(token_prefix=item[:20]):
                self.reject(item)
        with self.assertRaises(LicenseError):
            TrustedLicenseKeys('test-owner', {'test-key': self.private})
        with self.assertRaises(LicenseError):
            TrustedLicenseKeys('test-owner', {'test-key': test_key_pair()[1] + self.private})

    def test_deeply_nested_payload_is_a_redacted_invalid_license(self):
        header = '{"alg":"EdDSA","typ":"LH-FEATURE-LICENSE","kid":"test-key"}'
        token = self.raw_token(header, '[' * 5000 + '0' + ']' * 5000)
        self.assertLess(len(token), 16384)
        self.reject(token)

    def raw_token(self, header, payload):
        def enc(value):
            return base64.urlsafe_b64encode(value.encode()).rstrip(b'=')
        message = enc(header) + b'.' + enc(payload)
        key = serialization.load_pem_private_key(self.private, password=None)
        return (message + b'.' + base64.urlsafe_b64encode(key.sign(message)).rstrip(b'=')).decode()

    def test_duplicate_and_unexpected_json_fields_are_rejected(self):
        header = '{"alg":"EdDSA","typ":"LH-FEATURE-LICENSE","kid":"test-key"}'
        payload = json.dumps(self.payload)
        self.reject(self.raw_token(header[:-1] + ',"kid":"test-key"}', payload))
        self.reject(self.raw_token(header, payload[:-1] + ',"exp":100}'))
        for changes in ({'extra': 1}, {'aud': ['lead-hunter-feature-licenses']},
                        {'aud': 'other'}, {'iss': 'other'}, {'version': True},
                        {'jti': 'not-uuid'}, {'exp': True}, {'exp': 100.0},
                        {'exp': '100'}, {'iat': 20, 'nbf': 10}, {'nbf': 100},
                        {'workspace_id': None}):
            with self.subTest(changes=changes):
                self.reject(self.token({**self.payload, **changes}))
        for missing in self.payload:
            self.reject(self.token({k: v for k, v in self.payload.items() if k != missing}))

    def test_scope_and_features_must_match(self):
        self.reject(self.token(), 'license_subject_mismatch', managed_scope())
        for changes in ({'features': ['unknown']}, {'features': ['*']},
                        {'features': []}, {'features': ['diagnostics.full']*2},
                        {'features': 'diagnostics.full'}, {'installation_id': 123},
                        {'sub': str(managed_scope().subject_id)}):
            with self.subTest(changes=changes):
                self.reject(self.token({**self.payload, **changes}))
        scope = managed_scope()
        token = signed_test_license(license_claims(scope=scope), self.private)
        self.assertEqual(self.verifier.verify(token, scope=scope, now_epoch=10).scope, scope)
        self.reject(token, 'license_subject_mismatch', replace(scope, workspace_id=local_scope().installation_id))

    def test_epoch_values_must_be_representable_in_utc(self):
        for field in ('iat', 'nbf', 'exp'):
            for value in (-1, 253402300800, True, 1.5, '10'):
                with self.subTest(field=field, value=value):
                    self.reject(self.token({**self.payload, field: value}))
        claims = license_claims(issued_at=0, not_before=0, expires_at=253402300799)
        self.assertEqual(self.verifier.verify(signed_test_license(claims, self.private),
                                              scope=local_scope(), now_epoch=10).expires_at,
                         253402300799)

    def test_expired_license_metadata_requires_verified_signature(self):
        token = self.token()
        self.assertEqual(self.verifier.decode_verified(token, scope=local_scope()).expires_at, 100)
        with self.assertRaises(LicenseError) as caught:
            self.verifier.verify(token, scope=local_scope(), now_epoch=100)
        self.assertEqual(caught.exception.code, 'license_expired')
        with self.assertRaises(LicenseError):
            self.verifier.decode_verified(self.token(private=test_key_pair()[0]), scope=local_scope())
