from uuid import UUID

from src.domain.feature_licenses import AUDIENCE, LicenseClaims, LicenseScope, SubjectKind


def local_scope():
    return LicenseScope(UUID(int=1), SubjectKind.INSTALLATION, UUID(int=1))


def managed_scope():
    return LicenseScope(UUID(int=2), SubjectKind.WORKSPACE_USER, UUID(int=3), UUID(int=4))


def license_claims(*, scope=None, issued_at=0, not_before=0, expires_at=100,
                   features=("diagnostics.full",)):
    return LicenseClaims(1, "test-owner", AUDIENCE, UUID(int=5), issued_at, not_before,
                         expires_at, scope or local_scope(), features)


def test_key_pair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private = Ed25519PrivateKey.generate()
    return (private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()),
            private.public_key().public_bytes(serialization.Encoding.PEM,
                                              serialization.PublicFormat.SubjectPublicKeyInfo))


def claim_payload(claims):
    data = dict(version=claims.version, iss=claims.issuer, aud=claims.audience,
                jti=str(claims.license_id), iat=claims.issued_at, nbf=claims.not_before,
                exp=claims.expires_at, installation_id=str(claims.scope.installation_id),
                subject_kind=claims.scope.subject_kind.value, sub=str(claims.scope.subject_id),
                features=list(claims.features))
    if claims.scope.workspace_id is not None:
        data['workspace_id'] = str(claims.scope.workspace_id)
    return data


def signed_test_license(claims, private_pem, *, kid='test-key'):
    import jwt
    return jwt.encode(claim_payload(claims), private_pem, algorithm='EdDSA',
                      headers={'typ': 'LH-FEATURE-LICENSE', 'kid': kid})


class FakeClock:
    def __init__(self, epoch):
        self.epoch = epoch

    def now_epoch(self):
        return self.epoch

    def set(self, epoch):
        self.epoch = epoch
