"""Shared pytest fixtures for the Meeting-to-Scope Agent tests.

All unit tests run fully offline: an in-memory store, the deterministic rules
extractor, and a scriptable fake Knowledge Brain client. No network, no model.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.extractor import RuleBasedExtractor
from app.kb_client import KbAnswer, KbTimeout, KbUnavailable
from app.schemas import Citation, Indicator, Transcript
from app.service import MeetingToScopeService
from app.store import InMemoryStore
from app.transcript import new_transcript

CONSULTANT = {"name": "Sam", "side": "consultant"}
CUSTOMER = {"name": "Dana", "side": "customer"}


class FakeKB:
    """Scriptable Knowledge Brain client.

    Pass ``responses`` as a list of (substring, KbAnswer-or-exception-factory).
    The first substring found in the question wins. A default answer is returned
    when nothing matches.
    """

    def __init__(self, responses=None, default=None, *, reachable=True, calls=None):
        self.responses = responses or []
        self.default = default or KbAnswer(
            answer="No relevant documentation found.",
            evidence_status="insufficient",
            confidence=Indicator(level="none", score=0.0, basis="fake"),
        )
        self.reachable = reachable
        self.calls = calls if calls is not None else []
        self.closed = False

    def ping(self) -> bool:
        return self.reachable

    def ask(self, question, **kwargs):
        self.calls.append(question)
        for substring, response in self.responses:
            if substring.lower() in question.lower():
                if isinstance(response, Exception):
                    raise response
                if callable(response):
                    return response(question)
                return response
        return self.default

    def close(self):
        self.closed = True


def sufficient_answer(text="Supported.", score=0.9):
    return KbAnswer(
        answer=text,
        evidence_status="sufficient",
        citations=[Citation(article_id="a1", title="Doc", heading="H", chunk_id="c1", score=score)],
        confidence=Indicator(level="high", score=score, basis="fake kb"),
        request_id="req-1",
        model="fake-model",
    )


def insufficient_answer(text="No docs."):
    return KbAnswer(answer=text, evidence_status="insufficient", confidence=Indicator(level="none", score=0.0, basis="fake"))


def conflicting_answer(text="Conflicting docs."):
    return KbAnswer(answer=text, evidence_status="conflicting", confidence=Indicator(level="low", score=0.3, basis="fake"))


@pytest.fixture
def settings() -> Settings:
    return Settings(knowledge_brain_url="http://localhost:8000", extractor="rules")


@pytest.fixture
def fake_kb() -> FakeKB:
    return FakeKB()


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def service(store, fake_kb, settings) -> MeetingToScopeService:
    return MeetingToScopeService(store=store, extractor=RuleBasedExtractor(), kb_client=fake_kb, settings=settings)


def make_transcript(transcript_id="mtg-001", project_id="proj", segments=None, **kwargs) -> Transcript:
    segments = segments or [
        {"speaker": "Dana", "timestamp": "00:00:10", "text": "We need to support 50,000 members without slowing down."},
        {"speaker": "Dana", "timestamp": "00:01:00", "text": "We also need SAML SSO integration."},
        {"speaker": "Sam", "timestamp": "00:02:00", "text": "We could add a caching layer."},
    ]
    return new_transcript(
        transcript_id=transcript_id,
        project_id=project_id,
        meeting_date=kwargs.pop("meeting_date", "2026-01-01"),
        participants=[CUSTOMER, CONSULTANT],
        segments=segments,
        **kwargs,
    )


__all__ = [
    "FakeKB",
    "sufficient_answer",
    "insufficient_answer",
    "conflicting_answer",
    "make_transcript",
    "KbTimeout",
    "KbUnavailable",
]
