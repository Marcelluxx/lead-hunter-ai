"""Persistent time high-watermark shared by protected operations."""
import time
from typing import Protocol

from src.domain.feature_licenses import LicenseError, valid_epoch


class Clock(Protocol):
    def now_epoch(self) -> int: ...


class ClockStore(Protocol):
    def advance(self, observed_epoch: int) -> int: ...


class SystemClock:
    def now_epoch(self) -> int:
        return int(time.time())


class GuardedClock:
    def __init__(self, clock: Clock, store: ClockStore):
        self.clock, self.store = clock, store

    def now_epoch(self) -> int:
        observed = self.clock.now_epoch()
        if not valid_epoch(observed):
            raise LicenseError("license_clock_regression")
        maximum = self.store.advance(observed)
        if not valid_epoch(maximum) or maximum - observed > 300:
            raise LicenseError("license_clock_regression")
        return maximum
