"""Robots Exclusion Protocol for navigations initiated by LeadHunter."""
import asyncio
import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import monotonic
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import httpx

from .crawl_runtime import CrawlControlError

PRODUCT = "LeadHunter"
USER_AGENT = PRODUCT + "/1.0"
MAX_BODY = 512 * 1024
REDIRECTS = frozenset((301, 302, 303, 307, 308))
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_ESCAPES = re.compile(r"%[0-9a-fA-F]{2}")


def retry_delay(value):
    if not isinstance(value, str) or not value or len(value) > 80:
        return 0
    try:
        if value.strip().isascii() and value.strip().isdigit():
            return min(int(value), 86400)
        target = parsedate_to_datetime(value)
        if target.tzinfo is not None:
            return max(0, min(86400, (target - datetime.now(timezone.utc)).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        pass
    return 0


def _normalize(value):
    def escape(match):
        letter = chr(int(match[0][1:], 16))
        return letter if letter in _UNRESERVED else match[0].upper()
    encoded = quote(value, safe="/%!*'();:@&=+$,?[]~")
    return _ESCAPES.sub(escape, encoded)


@dataclass(frozen=True)
class _Rule:
    parts: tuple
    anchored: bool
    score: int
    allow: bool

    def matches(self, target):
        if len(self.parts) == 1:
            return target == self.parts[0] if self.anchored else target.startswith(self.parts[0])
        if not target.startswith(self.parts[0]):
            return False
        start, end = len(self.parts[0]), len(target)
        middle = self.parts[1:]
        if self.anchored:
            tail = middle[-1]
            if not target.endswith(tail):
                return False
            end -= len(tail)
            middle = middle[:-1]
        if start > end:
            return False
        for part in middle:
            if part:
                index = target.find(part, start, end)
                if index < 0:
                    return False
                start = index + len(part)
        return True


def _rules(body):
    groups = []
    agents, rules, found_directive = [], [], False
    for line in body.decode("utf-8-sig", errors="replace").splitlines():
        field, sep, value = line.split("#", 1)[0].partition(":")
        field, value = field.strip().lower(), value.strip()
        if not sep or "\ufffd" in value:
            continue
        if field == "user-agent" and value:
            if found_directive:
                groups.append((agents, rules))
                agents, rules, found_directive = [], [], False
            agents.append(value.casefold())
        elif field in ("allow", "disallow") and agents:
            found_directive = True
            if not value.startswith("/"):
                continue
            pattern = _normalize(value)
            anchored = pattern.endswith("$")
            pattern = pattern[:-1] if anchored else pattern
            parts = tuple(pattern.split("*"))
            size = len(re.findall(r"%[0-9A-F]{2}|.", "".join(parts)))
            rules.append(_Rule(parts, anchored, size, field == "allow"))
    if agents:
        groups.append((agents, rules))
    group = PRODUCT.casefold() if any(PRODUCT.casefold() in agents for agents, _ in groups) else "*"
    return tuple(rule for agents, rules in groups if group in agents for rule in rules)


@dataclass(frozen=True)
class RobotsResponse:
    status: int
    body: bytes = b""
    location: str = ""
    retry_after: str = ""


async def fetch_robots(decision):
    """Connect to an already validated IP and authenticate the original TLS name."""
    parsed = urlsplit(decision.normalized_url)
    ip = min(decision.resolved_ips, key=lambda addr: (":" in addr, addr))
    ip_authority = f"[{ip}]" if ":" in ip else ip
    endpoint = urlunsplit((parsed.scheme, f"{ip_authority}:{decision.port}", parsed.path, parsed.query, ""))
    # One connection pool per hop: IP sharing must not mix hostnames/SNI.
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=4) as client:
        async with client.stream("GET", endpoint, headers={"Host": parsed.netloc, "User-Agent": USER_AGENT,
                "Accept-Encoding": "identity"}, extensions={"sni_hostname": decision.hostname}) as response:
            body = bytearray()
            if response.status_code == 200:
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise CrawlControlError("robots_unavailable")
                async for chunk in response.aiter_raw(chunk_size=8192):
                    if len(body) + len(chunk) > MAX_BODY:
                        raise CrawlControlError("robots_unavailable")
                    body.extend(chunk)
            return RobotsResponse(response.status_code, bytes(body), response.headers.get("Location", ""),
                                  response.headers.get("Retry-After", ""))


class RobotsPolicy:
    def __init__(self, urls, *, fetch=fetch_robots, clock=monotonic):
        self.urls, self.fetch, self.clock = urls, fetch, clock
        self._cache = OrderedDict()
        self._cache_bytes = 0
        self._lock = asyncio.Lock()

    async def _load(self, origin, guard):
        url = origin + "/robots.txt"
        redirects = 0
        retried = False
        while True:
            guard()
            decision = await self.urls.validate_async(url)
            guard()
            try:
                response = await asyncio.wait_for(self.fetch(decision), 4)
            except (httpx.TransportError, asyncio.TimeoutError, OSError):
                response = RobotsResponse(503)
            guard()
            status = response.status
            if status in REDIRECTS and response.location and redirects < min(5, self.urls.max_redirects):
                target = urljoin(url, response.location)
                if urlsplit(url).scheme == "https" and urlsplit(target).scheme != "https":
                    return (), "robots_unavailable", 30, 0
                url, redirects = target, redirects + 1
                continue
            if status in (404, 410):
                return (), None, 900, 0
            if status == 200 and len(response.body) <= MAX_BODY:
                return _rules(response.body), None, 900, len(response.body)
            if status == 429:
                return (), "robots_rate_limited", max(60, retry_delay(response.retry_after)), 0
            if not retried and (status == 408 or 500 <= status <= 599):
                retried = True
                await asyncio.sleep(0.2)
                continue
            return (), "robots_unavailable", 30, 0

    async def require(self, decision, guard):
        async with self._lock:
            await self._require(decision, guard)

    async def _require(self, decision, guard):
        guard()
        parsed = urlsplit(decision.normalized_url)
        origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        cached = self._cache.get(origin)
        if cached is None or cached[0] <= self.clock():
            try:
                rules, error, ttl, size = await asyncio.wait_for(self._load(origin, guard), 10)
            except (asyncio.TimeoutError, CrawlControlError):
                rules, error, ttl, size = (), "robots_unavailable", 30, 0
            if cached is not None:
                self._cache_bytes -= cached[3]
            self._cache[origin] = (self.clock() + ttl, rules, error, size)
            self._cache_bytes += size
            self._cache.move_to_end(origin)
            while len(self._cache) > 512 or self._cache_bytes > 4 * 1024 * 1024:
                _, (_, _, _, removed) = self._cache.popitem(last=False)
                self._cache_bytes -= removed
        else:
            _, rules, error, _ = cached
            self._cache.move_to_end(origin)
        guard()
        if error:
            raise CrawlControlError(error)
        target = _normalize(parsed.path + ("?" + parsed.query if parsed.query else ""))
        best = max(((rule.score, rule.allow) for rule in rules if rule.matches(target)), default=(0, True))
        if not best[1]:
            raise CrawlControlError("robots_disallowed")
