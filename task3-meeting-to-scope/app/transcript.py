"""Transcript ingestion: parsing, validation, segmentation, and identity.

Transcripts may be supplied as structured JSON (preferred) or as plain text with
speaker labels. Every parse produces stable ``segment_id`` values and a
``content_hash`` so that re-processing the same transcript is idempotent and does
not create duplicate projects or requirements.

All transcript content is treated as untrusted data by the rest of the system.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.schemas import Participant, Transcript, TranscriptSegment, utcnow

# ``Speaker [00:01:23]: text`` or ``[00:01:23] Speaker: text`` or ``Speaker: text``
_SPEAKER_TS_AFTER = re.compile(
    r"^\s*(?P<speaker>[A-Z][\w .'\-]{0,60}?)\s*\[(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\]\s*:\s*(?P<text>.*)$"
)
_TS_SPEAKER_BEFORE = re.compile(
    r"^\s*\[(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<speaker>[A-Z][\w .'\-]{0,60}?)\s*:\s*(?P<text>.*)$"
)
_SPEAKER_ONLY = re.compile(
    r"^\s*(?P<speaker>[A-Z][\w .'\-]{0,60}?)\s*:\s*(?P<text>.*)$"
)


class TranscriptError(ValueError):
    """A transcript is empty, malformed, too long, or otherwise unusable."""


def content_hash(transcript: Transcript) -> str:
    payload = "\x1f".join(
        [
            transcript.project_id,
            transcript.transcript_id,
            transcript.meeting_date or "",
            transcript.combined_text(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _assign_segment_ids(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Give every segment a stable positional id when one is missing."""
    used: set[str] = set()
    out: list[TranscriptSegment] = []
    for index, seg in enumerate(segments, start=1):
        sid = (seg.segment_id or "").strip() or f"s{index:04d}"
        if sid in used:
            raise TranscriptError(f"duplicate segment_id: {sid}")
        used.add(sid)
        out.append(seg.model_copy(update={"segment_id": sid}))
    return out


def parse_transcript_text(
    text: str,
    *,
    transcript_id: str,
    project_id: str,
    title: str = "",
    meeting_date: str | None = None,
    participants: list[Participant] | None = None,
) -> Transcript:
    """Parse a plain-text transcript with speaker-labelled lines."""
    if text is None or not text.strip():
        raise TranscriptError("transcript text is empty")

    known = {p.name.lower() for p in (participants or [])}
    raw_segments: list[TranscriptSegment] = []
    current: dict | None = None

    for line in text.splitlines():
        if not line.strip():
            continue
        match = None
        for pattern in (_SPEAKER_TS_AFTER, _TS_SPEAKER_BEFORE, _SPEAKER_ONLY):
            m = pattern.match(line)
            if not m:
                continue
            speaker = m.group("speaker").strip()
            # Heuristic guard: prefer known participants; otherwise a name-like token.
            looks_like_name = len(speaker.split()) <= 5 and not speaker.strip().endswith("?")
            if known and speaker.lower() not in known and not looks_like_name:
                m = None
                continue
            match = m
            break

        if match:
            if current is not None:
                raw_segments.append(TranscriptSegment(**current))
            current = {
                "segment_id": "",
                "speaker": match.group("speaker").strip(),
                "timestamp": match.groupdict().get("ts"),
                "text": match.group("text").strip(),
            }
        elif current is not None:
            current["text"] = (current["text"] + " " + line.strip()).strip()
        else:
            # Preamble before any speaker line: keep as an unattributed segment.
            raw_segments.append(
                TranscriptSegment(segment_id="", speaker=None, timestamp=None, text=line.strip())
            )

    if current is not None:
        current["text"] = str(current["text"]).strip()
        if current["text"]:
            raw_segments.append(TranscriptSegment(**current))

    raw_segments = [seg for seg in raw_segments if seg.text.strip()]
    if not raw_segments:
        raise TranscriptError("no speaker-labelled segments could be parsed from text")

    segments = _assign_segment_ids(raw_segments)
    transcript = Transcript(
        transcript_id=transcript_id,
        project_id=project_id,
        title=title,
        meeting_date=meeting_date,
        participants=participants or [],
        segments=segments,
    )
    transcript.content_hash = content_hash(transcript)
    return transcript


def from_dict(payload: dict) -> Transcript:
    """Build a validated :class:`Transcript` from a JSON-like mapping."""
    if not isinstance(payload, dict):
        raise TranscriptError("transcript payload must be an object")
    data = dict(payload)
    segments_in = data.get("segments")
    if not isinstance(segments_in, list) or not segments_in:
        raise TranscriptError("transcript must contain a non-empty 'segments' list")
    try:
        segments = [TranscriptSegment(**seg) for seg in segments_in]
    except (ValidationError, TypeError) as exc:
        raise TranscriptError(f"invalid transcript segment: {exc}") from exc
    segments = _assign_segment_ids(segments)
    data["segments"] = [seg.model_dump() for seg in segments]
    data.setdefault("participants", [])
    try:
        transcript = Transcript(**data)
    except ValidationError as exc:
        raise TranscriptError(f"invalid transcript: {exc}") from exc
    transcript.content_hash = content_hash(transcript)
    return transcript


def validate_transcript(transcript: Transcript, *, max_chars: int) -> Transcript:
    """Reject empty, malformed, or excessively long transcripts."""
    if not transcript.transcript_id.strip():
        raise TranscriptError("transcript_id is required")
    if not transcript.project_id.strip():
        raise TranscriptError("project_id is required")
    if not transcript.segments:
        raise TranscriptError("transcript has no segments")
    total = len(transcript.combined_text())
    if total > max_chars:
        raise TranscriptError(
            f"transcript is too long: {total} characters exceeds limit {max_chars}"
        )
    if total == 0:
        raise TranscriptError("transcript has no readable content")
    return transcript


def load_transcript_file(
    path: str | Path, *, max_chars: int
) -> Transcript:
    """Load a transcript from a ``.json`` file (structured segments)."""
    p = Path(path)
    if not p.exists():
        raise TranscriptError(f"transcript file not found: {p}")
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TranscriptError(f"transcript file is not valid JSON: {p} ({exc})") from exc
    transcript = from_dict(payload)
    return validate_transcript(transcript, max_chars=max_chars)


def new_transcript(
    *,
    transcript_id: str,
    project_id: str,
    title: str = "",
    meeting_date: str | None = None,
    sequence: int = 1,
    parent_transcript_id: str | None = None,
    participants: list[dict] | None = None,
    segments: list[dict] | None = None,
    max_chars: int = 200000,
) -> Transcript:
    payload = {
        "transcript_id": transcript_id,
        "project_id": project_id,
        "title": title,
        "meeting_date": meeting_date,
        "sequence": sequence,
        "parent_transcript_id": parent_transcript_id,
        "participants": participants or [],
        "segments": segments or [],
    }
    transcript = from_dict(payload)
    return validate_transcript(transcript, max_chars=max_chars)
