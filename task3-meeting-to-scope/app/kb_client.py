"""Reusable client for the Task 1 Knowledge Brain ``POST /ask`` API.

Task 3 never re-implements retrieval; it calls the shared Knowledge Brain so that
feasibility assessments rest on the same evidence engine as the rest of the system.

The client preserves the KB's own honesty signals: an abstention (HTTP 200 with
``evidence_status`` of ``insufficient``/``unavailable``) is surfaced as such, never
upgraded to a positive answer. Transport failures and malformed payloads raise so
callers can record an explicit ``assessment_unavailable`` outcome instead of
pretending an assessment happened.

A live ``/ask`` call may be slow (a local model can take minutes to first token),
so the timeout is configurable. Citations are copied verbatim; nothing is invented.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

import httpx

from app.config import ConfigError, Settings
from app.schemas import Citation, Indicator

CONNECT_EXCEPTIONS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


class KbError(RuntimeError):
    """Base class for Knowledge Brain client failures."""


class KbConfigError(KbError, ConfigError):
    """The Knowledge Brain client is misconfigured."""


class KbUnavailable(KbError):
    """The Knowledge Brain could not be reached (connection refused, DNS, 5xx)."""


class KbTimeout(KbError):
    """The Knowledge Brain did not respond within the configured timeout."""


class KbResponseError(KbError):
    """The Knowledge Brain returned an unusable or unexpected payload."""


@dataclass
class KbAnswer:
    """Normalised view of a Task 1 ``/ask`` response."""

    answer: str
    evidence_status: str
    citations: list[Citation] = field(default_factory=list)
    confidence: Indicator | None = None
    needs_escalation: bool = False
    escalation_reason: str | None = None
    model: str | None = None
    request_id: str | None = None
    raw: dict | None = None


_VALID_EVIDENCE = {"sufficient", "insufficient", "conflicting", "unavailable"}


class KnowledgeBrainClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 60.0,
        max_retries: int = 1,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] | None = None,
        backoff_seconds: float = 1.0,
    ) -> None:
        if not base_url:
            raise KbConfigError("KNOWLEDGE_BRAIN_URL is required")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None
        self._sleeper = sleeper or time.sleep
        self._backoff_seconds = backoff_seconds

    # -- public API -----------------------------------------------------------

    def ask(
        self,
        question: str,
        *,
        top_k: int | None = None,
        min_score: float | None = None,
        include_chunks: bool = False,
    ) -> KbAnswer:
        body: dict = {"question": question, "include_chunks": include_chunks}
        if top_k is not None:
            body["top_k"] = top_k
        if min_score is not None:
            body["min_score"] = min_score

        payload = self._request("POST", "/ask", json=body)
        return self._parse_answer(payload)

    def ping(self) -> bool:
        """Return True when the Knowledge Brain responds to ``/health``."""
        try:
            response = self._client.get(f"{self.base_url}/health")
        except httpx.HTTPError:
            return False
        return response.status_code < 500 and response.status_code != 404

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # -- internals ------------------------------------------------------------

    def _request(self, method: str, path: str, *, json: dict) -> object:
        attempts = self.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self._client.request(method, f"{self.base_url}{path}", json=json)
            except (httpx.TimeoutException,) as exc:
                last_error = exc
                if attempt < attempts - 1:
                    self._sleeper(self._backoff_seconds * (2**attempt))
                    continue
                raise KbTimeout(f"knowledge brain timed out after {self.timeout}s") from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    self._sleeper(self._backoff_seconds * (2**attempt))
                    continue
                raise KbUnavailable(f"knowledge brain request failed: {exc.__class__.__name__}") from exc

            if 500 <= response.status_code < 600:
                last_error = KbUnavailable(f"retryable HTTP {response.status_code}")
                if attempt < attempts - 1:
                    self._sleeper(self._backoff_seconds * (2**attempt))
                    continue
                raise KbUnavailable(f"knowledge brain returned HTTP {response.status_code}")
            if response.status_code == 422:
                raise KbResponseError("knowledge brain rejected the request (HTTP 422)")
            if response.status_code >= 400:
                raise KbResponseError(f"knowledge brain returned HTTP {response.status_code}")

            try:
                return response.json()
            except ValueError as exc:
                raise KbResponseError("knowledge brain returned a non-JSON response") from exc

        raise KbUnavailable(f"knowledge brain request failed: {last_error}")

    @staticmethod
    def _parse_answer(payload: object) -> KbAnswer:
        if not isinstance(payload, dict):
            raise KbResponseError("knowledge brain response was not an object")
        status = str(payload.get("evidence_status", "unavailable")).lower()
        if status not in _VALID_EVIDENCE:
            status = "unavailable"

        citations: list[Citation] = []
        for item in payload.get("citations") or []:
            if not isinstance(item, dict):
                continue
            citations.append(
                Citation(
                    article_id=item.get("article_id"),
                    title=item.get("title"),
                    canonical_url=item.get("canonical_url"),
                    heading=item.get("heading"),
                    chunk_id=item.get("chunk_id"),
                    score=item.get("score"),
                )
            )

        confidence = None
        conf = payload.get("confidence")
        if isinstance(conf, dict):
            level = str(conf.get("level", "none")).lower()
            if level not in {"high", "medium", "low", "none"}:
                level = "none"
            try:
                score = float(conf.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            score = min(max(score, 0.0), 1.0)
            confidence = Indicator(level=level, score=score, basis=str(conf.get("basis", "from knowledge brain")))

        return KbAnswer(
            answer=str(payload.get("answer", "")),
            evidence_status=status,
            citations=citations,
            confidence=confidence,
            needs_escalation=bool(payload.get("needs_escalation", False)),
            escalation_reason=payload.get("escalation_reason"),
            model=payload.get("model"),
            request_id=payload.get("request_id"),
            raw=payload,
        )


def build_kb_client(settings: Settings, *, client: httpx.Client | None = None, sleeper: Callable[[float], None] | None = None) -> KnowledgeBrainClient:
    return KnowledgeBrainClient(
        settings.knowledge_brain_url,
        timeout=settings.knowledge_brain_timeout_seconds,
        max_retries=settings.knowledge_brain_retries,
        client=client,
        sleeper=sleeper,
    )
