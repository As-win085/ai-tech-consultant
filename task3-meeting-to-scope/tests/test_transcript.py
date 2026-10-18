"""Transcript ingestion: validation, source references, idempotency, text parsing."""

from __future__ import annotations

import pytest

from app.transcript import (
    TranscriptError,
    content_hash,
    from_dict,
    load_transcript_file,
    new_transcript,
    parse_transcript_text,
    validate_transcript,
)


def test_new_transcript_assigns_stable_segment_ids():
    t = new_transcript(
        transcript_id="t1",
        project_id="p1",
        segments=[{"speaker": "A", "text": "First line here."}, {"speaker": "B", "text": "Second line here."}],
    )
    assert [s.segment_id for s in t.segments] == ["s0001", "s0002"]
    # reprocessing yields identical ids
    t2 = new_transcript(
        transcript_id="t1",
        project_id="p1",
        segments=[{"speaker": "A", "text": "First line here."}, {"speaker": "B", "text": "Second line here."}],
    )
    assert [s.segment_id for s in t2.segments] == [s.segment_id for s in t.segments]


def test_content_hash_is_stable_and_changes_with_content():
    a = new_transcript(transcript_id="t1", project_id="p1", segments=[{"speaker": "A", "text": "Hello world."}])
    b = new_transcript(transcript_id="t1", project_id="p1", segments=[{"speaker": "A", "text": "Hello world."}])
    c = new_transcript(transcript_id="t1", project_id="p1", segments=[{"speaker": "A", "text": "Different text."}])
    assert a.content_hash == b.content_hash
    assert a.content_hash != c.content_hash
    assert content_hash(a) == a.content_hash


def test_empty_transcript_rejected():
    with pytest.raises(TranscriptError):
        parse_transcript_text("", transcript_id="t", project_id="p")


def test_malformed_transcript_rejected():
    with pytest.raises(TranscriptError):
        from_dict({"transcript_id": "t", "project_id": "p", "segments": "not-a-list"})
    with pytest.raises(TranscriptError):
        from_dict({"transcript_id": "t", "project_id": "p", "segments": [{"speaker": "A"}]})  # missing text


def test_duplicate_segment_ids_rejected():
    with pytest.raises(TranscriptError):
        from_dict(
            {
                "transcript_id": "t",
                "project_id": "p",
                "segments": [
                    {"segment_id": "x", "speaker": "A", "text": "One two three."},
                    {"segment_id": "x", "speaker": "B", "text": "Four five six."},
                ],
            }
        )


def test_too_long_transcript_rejected():
    segments = [{"speaker": "A", "text": "word " * 50} for _ in range(5)]
    with pytest.raises(TranscriptError):
        new_transcript(transcript_id="t", project_id="p", segments=segments, max_chars=100)


def test_text_parsing_supports_speaker_and_timestamp_formats():
    text = (
        "Dana [00:01:00]: We need the first thing.\n"
        "[00:02:00] Sam: We could do the second thing.\n"
        "Dana: And a third thing as a follow-up.\n"
    )
    t = parse_transcript_text(text, transcript_id="t", project_id="p")
    assert len(t.segments) == 3
    assert t.segments[0].speaker == "Dana"
    assert t.segments[0].timestamp == "00:01:00"
    assert t.segments[1].speaker == "Sam"
    assert t.segments[2].text.startswith("And a third thing")


def test_load_transcript_file(tmp_path):
    import json

    path = tmp_path / "t.json"
    path.write_text(
        json.dumps(
            {
                "transcript_id": "t1",
                "project_id": "p1",
                "segments": [{"speaker": "Dana", "text": "We need a thing."}],
            }
        ),
        encoding="utf-8",
    )
    t = load_transcript_file(path, max_chars=200000)
    assert t.segments[0].segment_id == "s0001"


def test_validate_rejects_blank_project():
    t = new_transcript(transcript_id="t1", project_id="p1", segments=[{"speaker": "A", "text": "Some text here."}])
    t.project_id = ""
    with pytest.raises(TranscriptError):
        validate_transcript(t, max_chars=200000)
