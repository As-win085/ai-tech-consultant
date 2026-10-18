"""Shared test configuration.

Disables the process-wide model-request throttle delay so provider unit tests
run in milliseconds instead of pacing requests against LLM_MIN_DELAY_MS.
"""

import pytest


@pytest.fixture(autouse=True)
def _no_throttle_delay(monkeypatch):
    monkeypatch.setenv("LLM_MIN_DELAY_SECONDS", "0")
