"""Redis-backed fixed-window rate limiter."""

from __future__ import annotations

from redis import Redis


class RateLimitExceeded(RuntimeError):
    pass


class RedisRateLimiter:
    def __init__(self, client: Redis):
        self._client = client

    def require(self, *, scope: str, subject: str, limit: int, window_seconds: int) -> None:
        key = f"ratelimit:{scope}:{subject}"
        with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            count, _ = pipe.execute()
        if int(count) > limit:
            raise RateLimitExceeded("Limite richieste superato.")
