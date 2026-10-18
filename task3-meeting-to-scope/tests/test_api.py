"""API tests using in-process HTTPX ASGI transport (no loopback socket required)."""

from __future__ import annotations

import asyncio
import httpx

from app.main import app, get_service
from app.service import MeetingToScopeService
from app.store import InMemoryStore
from app.extractor import RuleBasedExtractor
from tests.conftest import FakeKB, sufficient_answer


class SyncASGIClient:
    def __init__(self, application):
        self.application = application

    def request(self, method, url, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=self.application, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as session:
                return await session.request(method, url, **kwargs)
        return asyncio.run(send())

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


def make_client():
    # Override the real get_service (which loads .env and may build an LLM
    # extractor that makes live network calls) with a deterministic test service.
    # The service is created once and shared across requests in the same test
    # so state (e.g. ingested transcripts) persists between calls.
    service = _svc()
    app.dependency_overrides[get_service] = lambda: service
    return SyncASGIClient(app)


def _svc():
    return MeetingToScopeService(store=InMemoryStore(), extractor=RuleBasedExtractor(), kb_client=FakeKB([("sso", sufficient_answer())]))


def test_root_and_health():
    client = make_client()
    r = client.get("/")
    assert r.status_code == 200
    r = client.get("/health")
    assert r.status_code == 200
    r = client.get("/ready")
    assert r.status_code == 200


def test_ui_endpoint_returns_html():
    client = make_client()
    r = client.get("/ui")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_ingest_transcript_via_api():
    client = make_client()
    payload = {
        "project_id": "proj",
        "transcript_id": "mtg-001",
        "participants": [{"name": "Dana", "side": "customer"}, {"name": "Sam", "side": "consultant"}],
        "segments": [
            {"speaker": "Dana", "text": "We need to support 50,000 members."},
            {"speaker": "Dana", "text": "We also need SAML SSO integration."},
        ],
    }
    r = client.post("/transcripts", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert len(data["requirements"]) == 2
    assert data["transcript"]["project_id"] == "proj"


def test_list_requirements_and_feasibility():
    client = make_client()
    client.post(
        "/transcripts",
        json={
            "project_id": "proj2",
            "transcript_id": "mtg-001",
            "participants": [{"name": "Dana", "side": "customer"}, {"name": "Sam", "side": "consultant"}],
            "segments": [{"speaker": "Dana", "text": "We need to support 50,000 members."}, {"speaker": "Dana", "text": "We also need SAML SSO integration."}],
        },
    )
    r = client.get("/projects/proj2/requirements")
    assert r.status_code == 200
    reqs = r.json()
    assert len(reqs) == 2
    rid = reqs[0]["requirement_id"]
    r = client.get(f"/requirements/{rid}")
    assert r.status_code == 200
    r = client.post("/projects/proj2/feasibility")
    assert r.status_code == 200
    r = client.post("/projects/proj2/proposals")
    assert r.status_code == 201


def test_review_actions():
    client = make_client()
    client.post(
        "/transcripts",
        json={
            "project_id": "proj3",
            "transcript_id": "mtg-001",
            "participants": [{"name": "Dana", "side": "customer"}, {"name": "Sam", "side": "consultant"}],
            "segments": [{"speaker": "Dana", "text": "We need to support 50,000 members."}],
        },
    )
    reqs = client.get("/projects/proj3/requirements").json()
    rid = reqs[0]["requirement_id"]
    r = client.post(f"/requirements/{rid}/review", json={"to_status": "approved", "actor": "pm"})
    assert r.status_code == 200
    r = client.post("/projects/proj3/baselines", json={"approved_by": "pm"})
    assert r.status_code == 201
    r = client.get("/projects/proj3/baselines")
    assert r.status_code == 200


def test_invalid_transcript_returns_422():
    client = make_client()
    r = client.post("/transcripts", json={"project_id": "p", "transcript_id": "t", "segments": []})
    assert r.status_code == 422


def test_unknown_resource_returns_404():
    client = make_client()
    r = client.get("/requirements/nope")
    assert r.status_code == 404


def test_validation_error_returns_422():
    client = make_client()
    r = client.post("/transcripts", json={"project_id": "p"})  # missing transcript_id/segments/text
    assert r.status_code == 422
