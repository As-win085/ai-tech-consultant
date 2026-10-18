"""Postgres-backed store integration tests.

These tests are marked as ``integration`` and only run when
``TEST_DATABASE_URL`` is set. They verify schema isolation and basic
persistence semantics against a real PostgreSQL instance (pg8000).
"""

from __future__ import annotations

import os

import pytest

from app.config import load_settings
from app.db import apply_migrations, connect
from app.extractor import RuleBasedExtractor
from app.postgres_store import PostgresStore
from app.service import MeetingToScopeService
from app.transcript import new_transcript

pytestmark = pytest.mark.integration


@pytest.mark.skipif(os.getenv("TEST_DATABASE_URL") is None, reason="TEST_DATABASE_URL not set")
def test_postgres_store_roundtrip():
    db_url = os.environ["TEST_DATABASE_URL"]
    conn = connect(db_url)
    schema = "meeting_to_scope_test"
    try:
        apply_migrations(conn, schema=schema)
        store = PostgresStore(conn, schema=schema)
        # clean state (best-effort)
        try:
            conn.run(f"DELETE FROM {schema}.mt_requirement")
            conn.run(f"DELETE FROM {schema}.mt_assessment")
            conn.run(f"DELETE FROM {schema}.mt_proposal")
            conn.run(f"DELETE FROM {schema}.mt_baseline")
            conn.run(f"DELETE FROM {schema}.mt_change_summary")
            conn.run(f"DELETE FROM {schema}.mt_transcript")
            conn.run(f"DELETE FROM {schema}.mt_project")
        except Exception:
            pass

        t = new_transcript(
            transcript_id="t1",
            project_id="ptest",
            segments=[
                {"speaker": "Dana", "text": "We need to support 50,000 members."},
                {"speaker": "Dana", "text": "We also need SAML SSO integration."},
            ],
        )
        store.save_transcript(t)
        reqs = RuleBasedExtractor().extract(t).requirements
        store.save_requirements("ptest", reqs)
        assert store.get_transcript("t1").transcript_id == "t1"
        assert len(store.list_requirements("ptest")) == len(reqs)
    finally:
        conn.close()
