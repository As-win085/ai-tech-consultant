"""Process-wide serialization and pacing for model-provider requests."""

from __future__ import annotations

import os
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterator
from dotenv import dotenv_values
import httpx


def _setting(name: str, default: str) -> str:
    if name in os.environ:
        return os.environ[name]
    try:
        return str(dotenv_values(".env").get(name) or default)
    except (OSError, ValueError):
        return default


class ModelRequestThrottle:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_started = 0.0

    @staticmethod
    def min_delay_seconds() -> float:
        value = _setting("LLM_MIN_DELAY_SECONDS", "")
        if value is not None:
            if value:
                return max(0.0, float(value))
        return max(0.0, float(_setting("LLM_MIN_DELAY_MS", _setting("LLM_REQUEST_DELAY_MS", "8000"))) / 1000)

    @contextmanager
    def request(self) -> Iterator[None]:
        self._lock.acquire()
        try:
            delay = self.min_delay_seconds()
            wait = delay - (time.monotonic() - self._last_started)
            if wait > 0:
                time.sleep(wait)
            self._last_started = time.monotonic()
            yield
        finally:
            self._lock.release()


MODEL_REQUEST_THROTTLE = ModelRequestThrottle()


def retry_delay_seconds(retry_after: str | None, attempt: int, base: float = 1.0) -> float:
    cap = max(0.0, float(_setting("LLM_BACKOFF_CAP_SECONDS", "60")))
    delay = min(cap, max(0.0, base) * (2**attempt))
    if not retry_after:
        return delay
    try:
        requested = max(0.0, float(retry_after.strip()))
    except ValueError:
        try:
            at = parsedate_to_datetime(retry_after)
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            requested = max(0.0, (at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return delay
    # A provider Retry-After wins; cap applies to exponential backoff only.
    return max(delay, requested)


def response_retry_after(response: httpx.Response) -> str | None:
    header = response.headers.get("Retry-After")
    if header:
        return header
    try:
        payload = response.json()
        details = payload.get("error", {}).get("details", [])
        for detail in details if isinstance(details, list) else []:
            if isinstance(detail, dict) and str(detail.get("@type", "")).endswith("RetryInfo"):
                value = detail.get("retryDelay")
                if isinstance(value, str):
                    match = re.fullmatch(r"(\d+(?:\.\d+)?)s", value)
                    return match.group(1) if match else None
    except (ValueError, AttributeError, TypeError):
        pass
    return None
