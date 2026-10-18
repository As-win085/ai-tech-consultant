"""API tests using FastAPI TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.service import MeetingToScopeService
from app.store import InMemoryStore
from app.extractor import RuleBasedExtractor
from tests.conftest import FakeKB, sufficient_answer


def _svc():
    return MeetingToScopeService(store=InMemoryStore(), extractor=RuleBasedExtractor(), kb_client=FakeKB([("sso", sufficient_answer())]))


def test_root_and_health():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    r = client.get("/health")
    assert r.status_code == 200
    r = client.get("/ready")
    assert r.status_code == 200


def test_ui_endpoint_returns_html():
    client = TestClient(app)
    r = client.get("/ui")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_ingest_transcript_via_api():
    client = TestClient(app)
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
    client = TestClient(app)
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
    client = TestClient(app)
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
    client = TestClient(app)
    r = client.post("/transcripts", json={"project_id": "p", "transcript_id": "t", "segments": []})
    assert r.status_code == 422


def test_unknown_resource_returns_404():
    client = TestClient(app)
    r = client.get("/requirements/nope")
    assert r.status_code == 404


def test_validation_error_returns_422():
    client = TestClient(app)
    r = client.post("/transcripts", json={"project_id": "p"})  # missing transcript_id/segments/text
    assert r.status_code == 422
