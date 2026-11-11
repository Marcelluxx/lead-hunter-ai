"""Per-crawler operational limits, independent of the browser provider."""
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from math import isfinite
from time import monotonic


class CrawlControlError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CrawlLimits:
    navigations_per_host: int = 24
    host_window_seconds: float = 60
    browser_requests: int = 160
    page_seconds: float = 25
    crawl_seconds: float = 90
    retries: int = 1
    cooldown_seconds: float = 60
    failure_threshold: int = 2

    def __post_init__(self):
        for value, lower, upper in ((self.navigations_per_host, 1, 200),
                                    (self.browser_requests, 1, 1000),
                                    (self.retries, 0, 1), (self.failure_threshold, 1, 10)):
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError("crawler_limits_invalid")
        for value in (self.host_window_seconds, self.page_seconds, self.crawl_seconds, self.cooldown_seconds):
            if type(value) not in (int, float) or not 0 < value <= 3600 or not isfinite(value):
                raise ValueError("crawler_limits_invalid")


@dataclass
class _Host:
    attempts: deque = field(default_factory=deque)
    failures: int = 0
    blocked_until: float = 0
    last_seen: float = 0


class CrawlRuntime:
    def __init__(self, limits, *, clock=monotonic):
        self.limits = limits
        self.clock = clock
        self._hosts = OrderedDict()

    def _host(self, name):
        now = self.clock()
        state = self._hosts.get(name)
        if state is None:
            if len(self._hosts) >= 512:
                horizon = max(self.limits.cooldown_seconds, self.limits.host_window_seconds)
                stale = next((key for key, value in self._hosts.items()
                              if now - value.last_seen >= horizon and value.blocked_until <= now), None)
                if stale is None:
                    raise CrawlControlError("domain_state_capacity")
                self._hosts.pop(stale)
            state = self._hosts[name] = _Host()
        state.last_seen = now
        self._hosts.move_to_end(name)
        return state, now

    def require(self, name, *, consume=False):
        state, now = self._host(name)
        if state.blocked_until > now:
            raise CrawlControlError("domain_cooldown")
        if state.blocked_until:
            state.blocked_until = 0
            state.failures = 0
        while state.attempts and now - state.attempts[0] >= self.limits.host_window_seconds:
            state.attempts.popleft()
        if len(state.attempts) >= self.limits.navigations_per_host:
            raise CrawlControlError("domain_budget_exhausted")
        if consume:
            state.attempts.append(now)

    def outcome(self, name, *, transient=False, rate_limited=False, retry_after=0):
        state, now = self._host(name)
        state.failures = state.failures + 1 if transient else 0
        if rate_limited or state.failures >= self.limits.failure_threshold:
            state.blocked_until = now + max(self.limits.cooldown_seconds, retry_after)
