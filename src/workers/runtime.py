"""Dramatiq CLI module: configure Redis before importing actors."""

from __future__ import annotations

import os

from .broker import configure_broker


configure_broker(os.environ["LEADHUNTER_REDIS_URL"])

from .broker import process_job  # noqa: E402,F401
from .retention import enforce_workspace_retention  # noqa: E402,F401
