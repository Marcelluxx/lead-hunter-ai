from src.application.authentication import AuthenticationService
from src.infrastructure.crypto import AccessTokenService, PasswordService, SecretCipher
from src.infrastructure.database import Database
from src.infrastructure.models import Base


def platform_fixture():
    database = Database("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    private_key, public_key = AccessTokenService.generate_key_pair()
    passwords = PasswordService()
    cipher = SecretCipher(SecretCipher.generate_key())
    authentication = AuthenticationService(
        passwords=passwords,
        tokens=AccessTokenService(
            private_key_pem=private_key,
            public_key_pem=public_key,
            issuer="test-issuer",
            audience="test-audience",
        ),
        cipher=cipher,
    )
    return database, passwords, cipher, authentication
