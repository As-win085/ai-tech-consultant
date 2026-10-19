"""Prompts for LLM-backed requirement extraction.

The transcript is treated as untrusted input: the system prompt states that any
instructions embedded in the transcript are data, never commands. The model is
told to mark uncertainty rather than invent commitments, budgets, deadlines,
constraints or acceptance criteria.

The system prompt text is versioned: see prompts/extraction_system.vN.md and
prompts/active.json, loaded through app.promptstore (schema prompt/v1).
"""

from __future__ import annotations

from app.promptstore import LoadedPrompt, load_prompt
from app.schemas import Transcript

EXTRACTION_PROMPT: LoadedPrompt = load_prompt("extraction_system")
EXTRACTION_SYSTEM_PROMPT: str = EXTRACTION_PROMPT.text


def build_extraction_user_prompt(transcript: Transcript, *, max_chars: int = 200_000) -> str:
    lines = [
        f"Project: {transcript.project_id}",
        f"Transcript: {transcript.transcript_id}",
        f"Date: {transcript.meeting_date or 'unknown'}",
        "Participants: " + ", ".join(f"{p.name} ({p.side})" for p in transcript.participants),
    ]
    context = getattr(transcript, "context", None)
    if context and getattr(context, "notes", None):
        lines.append(f"Context: {context.notes}")
    lines.append("")
    lines.append("Segments:")
    text = transcript.combined_text()
    if len(text) > max_chars:
        text = text[:max_chars]
    for segment in transcript.segments:
        stamp = f" {segment.timestamp}" if segment.timestamp else ""
        lines.append(f"[{segment.segment_id}] {segment.speaker}{stamp}: {segment.text}")
    lines.append("")
    lines.append("Return the JSON array of requirements now.")
    return "\n".join(lines)
