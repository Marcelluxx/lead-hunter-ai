"""Production API composition root used by Uvicorn's factory mode."""

from __future__ import annotations

from redis import Redis

from .application.authentication import AuthenticationService
from .application.budgets import BudgetService
from .application.jobs import JobService
from .application.secrets import CredentialService
from .infrastructure.crypto import AccessTokenService, PasswordService, SecretCipher
from .infrastructure.database import Database
from .infrastructure.redis import RedisRateLimiter
from .web.app import create_app
from .web.dependencies import WebRuntime
from .web.settings import ServerSettings
from .workers.broker import DramatiqJobPublisher, configure_broker


def create_server_app():
    settings = ServerSettings()
    database = Database(settings.database_url)
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    configure_broker(settings.redis_url)
    cipher = SecretCipher(settings.master_key())
    authentication = AuthenticationService(
        passwords=PasswordService(),
        tokens=AccessTokenService(
            private_key_pem=settings.private_key(),
            public_key_pem=settings.public_key(),
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        ),
        cipher=cipher,
    )
    budgets = BudgetService()
    return create_app(
        WebRuntime(
            database=database,
            authentication=authentication,
            jobs=JobService(budgets=budgets, publisher=DramatiqJobPublisher()),
            budgets=budgets,
            credentials=CredentialService(cipher),
            rate_limiter=RedisRateLimiter(redis_client),
        )
    )
