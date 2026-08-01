"""Policy fail-closed per gli URL visitati dal crawler.

La validazione viene applicata sia alle navigazioni esplicite sia alle richieste
generate dal browser (redirect, script, iframe e altre sub-risorse).
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import threading
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Sequence
from urllib.parse import urlsplit, urlunsplit


Resolver = Callable[..., Sequence[tuple]]


class UrlPolicyError(ValueError):
    """URL rifiutato dalla policy di rete."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class UrlDecision:
    """Risultato immutabile di una validazione URL."""

    normalized_url: str
    hostname: str
    port: int
    resolved_ips: tuple[str, ...]


class SafeUrlPolicy:
    """Valida URL e DNS, bloccando destinazioni non pubbliche.

    Per ogni hostname viene memorizzato il primo insieme di indirizzi osservato.
    Una variazione durante lo stesso ciclo di vita della policy viene trattata
    come possibile DNS rebinding e causa il blocco.
    """

    def __init__(
        self,
        *,
        allowed_ports: Iterable[int] = (80, 443),
        max_redirects: int = 5,
        resolver: Resolver = socket.getaddrinfo,
        max_url_length: int = 2048,
    ):
        self.allowed_ports = frozenset(int(port) for port in allowed_ports)
        self.max_redirects = max(0, int(max_redirects))
        self._resolver = resolver
        self.max_url_length = max_url_length
        self._dns_pins: dict[str, frozenset[str]] = {}
        self._dns_pin_lock = threading.Lock()

    def reset_dns_pins(self) -> None:
        """Apre una nuova sessione logica di crawl."""

        with self._dns_pin_lock:
            self._dns_pins.clear()

    def validate(
        self,
        url: str,
        *,
        allowed_hosts: Optional[Iterable[str]] = None,
    ) -> UrlDecision:
        """Valida schema, credenziali, porta, hostname e tutte le risposte DNS."""

        if not isinstance(url, str) or not url.strip():
            raise UrlPolicyError("empty_url", "URL assente.")
        if len(url) > self.max_url_length:
            raise UrlPolicyError("url_too_long", "URL troppo lungo.")
        if url != url.strip() or any(ord(char) < 32 for char in url):
            raise UrlPolicyError("invalid_characters", "URL con caratteri di controllo o spazi esterni.")

        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"}:
            raise UrlPolicyError("invalid_scheme", "Sono consentiti esclusivamente URL HTTP e HTTPS.")
        if parsed.username is not None or parsed.password is not None:
            raise UrlPolicyError("credentials_forbidden", "Le credenziali nell'URL non sono consentite.")
        if not parsed.hostname:
            raise UrlPolicyError("missing_hostname", "Hostname mancante.")

        try:
            hostname = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise UrlPolicyError("invalid_hostname", "Hostname non valido.") from exc

        if not hostname or hostname == "localhost" or hostname.endswith(".localhost"):
            raise UrlPolicyError("local_hostname", "Hostname locale non consentito.")

        try:
            port = parsed.port or (443 if scheme == "https" else 80)
        except ValueError as exc:
            raise UrlPolicyError("invalid_port", "Porta URL non valida.") from exc
        if port not in self.allowed_ports:
            raise UrlPolicyError("port_forbidden", f"Porta {port} non consentita.")

        if allowed_hosts is not None:
            normalized_allowed = {
                host.rstrip(".").encode("idna").decode("ascii").lower()
                for host in allowed_hosts
            }
            if hostname not in normalized_allowed:
                raise UrlPolicyError("host_forbidden", "Il link non appartiene al sito autorizzato.")

        addresses = self._resolve_public_addresses(hostname, port)
        current = frozenset(addresses)
        with self._dns_pin_lock:
            previous = self._dns_pins.get(hostname)
            if previous is not None and previous != current:
                raise UrlPolicyError("dns_rebinding", "La risoluzione DNS è cambiata durante il crawl.")
            self._dns_pins[hostname] = current

        netloc = hostname
        if ":" in hostname:
            netloc = f"[{hostname}]"
        default_port = 443 if scheme == "https" else 80
        if port != default_port:
            netloc = f"{netloc}:{port}"

        normalized = urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))
        return UrlDecision(normalized, hostname, port, tuple(sorted(addresses)))

    async def validate_async(
        self,
        url: str,
        *,
        allowed_hosts: Optional[Iterable[str]] = None,
    ) -> UrlDecision:
        """Esegue la risoluzione DNS fuori dall'event loop del browser."""

        return await asyncio.to_thread(self.validate, url, allowed_hosts=allowed_hosts)

    def _resolve_public_addresses(self, hostname: str, port: int) -> set[str]:
        try:
            literal = ipaddress.ip_address(hostname)
            raw_addresses = {str(literal)}
        except ValueError:
            try:
                records = self._resolver(hostname, port, type=socket.SOCK_STREAM)
            except (OSError, socket.gaierror) as exc:
                raise UrlPolicyError("dns_failure", "Impossibile risolvere l'hostname.") from exc
            raw_addresses = {
                str(record[4][0]).split("%", 1)[0]
                for record in records
                if len(record) >= 5 and record[4]
            }

        if not raw_addresses:
            raise UrlPolicyError("dns_empty", "La risoluzione DNS non ha restituito indirizzi.")

        normalized: set[str] = set()
        for raw_address in raw_addresses:
            try:
                address = ipaddress.ip_address(raw_address)
            except ValueError as exc:
                raise UrlPolicyError("invalid_ip", "La risoluzione DNS ha restituito un IP non valido.") from exc

            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                address = address.ipv4_mapped
            if not address.is_global:
                raise UrlPolicyError(
                    "non_public_ip",
                    "Destinazione privata, locale, riservata o non instradabile.",
                )
            normalized.add(str(address))

        return normalized
