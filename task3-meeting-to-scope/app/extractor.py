"""Requirement extraction from meeting transcripts.

The extractor is pluggable:

* :class:`RuleBasedExtractor` — deterministic, offline, no model calls. It reads
  cue phrases and speaker context to turn transcript segments into structured
  requirements. This is the shipped default.
* :class:`LlmExtractor` — asks a configurable chat model for a JSON array of
  requirements, then validates/normalises the result against the schema.

Both produce the same :class:`~app.schemas.Requirement` objects. The rules
extractor is intentionally conservative: it prefers creating an *open question*
or marking a statement *uncertain* over inventing a customer commitment.

Conflict detection (:func:`detect_conflicts`) preserves contradictory statements
and links them instead of silently choosing one.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.config import Settings
from app.schemas import (
    Indicator,
    Requirement,
    RequirementType,
    SourceRef,
    StatementKind,
    Transcript,
    utcnow,
)

# --- Cue phrase sets ---------------------------------------------------------

REQUEST_CUES = (
    "we need",
    "we also need",
    "we'll need",
    "we will need",
    "we still need",
    "we want",
    "we also want",
    "we'd want",
    "we would want",
    "we'd like",
    "we would like",
    "we require",
    "we're looking for",
    "we are looking for",
    "must be able to",
    "needs to be able to",
    "need to be able to",
    "should be able to",
    "should support",
    "needs to support",
    "has to",
    "have to",
    "can you add",
    "could you add",
    "can you make",
    "please add",
    "please make",
    "let's add",
    "let's build",
    "we need to add",
    "the system must",
    "the platform must",
    "the site must",
    "it must",
)
INTEGRATION_CUES = (
    "integrat",
    "sso",
    "saml",
    "oauth",
    "oidc",
    "single sign-on",
    "api",
    "webhook",
    "sync with",
    "third-party",
    "payment gateway",
    "crm",
    "zapier",
    "scim",
)
NONFUNCTIONAL_CUES = (
    "performance",
    "latency",
    "response time",
    "scalab",
    "scale to",
    "concurrent",
    "uptime",
    "availability",
    "sla",
    "gdpr",
    "compliance",
    "pci",
    "soc 2",
    "soc2",
    "security",
    "encrypt",
    "audit log",
    "accessib",
    "backup",
    "members",
    "load",
)
CONSTRAINT_CUES = (
    "deadline",
    "before the",
    "by the end of",
    "budget",
    "cannot",
    "can't",
    "must not",
    "not allowed",
    "constraint",
    "only support",
    "we're limited",
    "we are limited",
    "regulatory",
    "legal requirement",
)
ASSUMPTION_CUES = (
    "i assume",
    "we assume",
    "presumably",
    "i expect",
    "we expect",
    "should already",
    "i guess",
    "i imagine",
)
OPEN_QUESTION_CUES = (
    "not sure",
    "we're not sure",
    "tbd",
    "decide later",
    "clarify",
    "unclear",
    "open question",
    "we'll figure out",
    "find out",
    "need to check whether",
    "does it support",
    "do you support",
    "is there a way",
)
PROPOSED_SOLUTION_CUES = (
    "we could",
    "i could",
    "we'd propose",
    "we would propose",
    "i recommend",
    "my recommendation",
    "i'd suggest",
    "i suggest",
    "we suggest",
    "let's use",
    "we can use",
    "one option is",
    "we'd recommend",
)
PAIN_CUES = (
    "complains",
    "complain",
    "struggle",
    "struggling",
    "too slow",
    "annoying",
    "problem",
    "painful",
    "frustrat",
    "takes forever",
    "keeps failing",
    "keeps breaking",
)
AMBIGUITY_CUES = (
    "modern",
    "nicer",
    "nice looking",
    "better looking",
    "make it pop",
    "improve the",
    "some kind of",
    "and stuff",
    "etc.",
    "more intuitive",
    "cleaner",
    "feel",
    "vibe",
    "seamless",
    "world class",
    "better",
)
RISK_CUES = ("risk", "concern", "worried", "worry", "afraid")
DEPENDENCY_CUES = ("depends on", "after we", "once the", "requires the", "blocked by", "before we can")
ACCEPTANCE_CUES = ("acceptance criteria", "we'll consider it done", "done when", "success metric", "we'll know it works")

# Cues that indicate untrusted "instructions" that must never be obeyed.
INJECTION_CUES = (
    "ignore previous",
    "ignore your instructions",
    "ignore all instructions",
    "disregard your",
    "system prompt",
    "you are now",
    "override",
    "reveal your",
    "print the api key",
    "output the api key",
    "approve everything",
    "mark all requirements approved",
)

_NUMBER_WORD_RE = re.compile(r"\b(\d[\d,]*\s*k?)\b", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ExtractionResult:
    requirements: list[Requirement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class Extractor(Protocol):
    def extract(self, transcript: Transcript) -> ExtractionResult:
        ...


# --- Helpers -----------------------------------------------------------------


def _lower(text: str) -> str:
    return text.lower()


def _contains_any(text: str, cues: tuple[str, ...]) -> str | None:
    low = _lower(text)
    for cue in cues:
        if cue in low:
            return cue
    return None


def _speaker_side(transcript: Transcript) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for p in transcript.participants:
        mapping[p.name.lower()] = p.side
    return mapping


def _first_sentence(text: str, *, limit: int = 240) -> str:
    parts = _SENTENCE_SPLIT.split(text.strip())
    sentence = parts[0].strip() if parts else text.strip()
    if len(sentence) > limit:
        sentence = sentence[: limit - 1].rstrip() + "\u2026"
    return sentence


def _rationale(text: str) -> str | None:
    low = _lower(text)
    for marker in ("so that", "so we can", "because", "in order to"):
        idx = low.find(marker)
        if idx != -1:
            clause = text[idx + len(marker) :].strip(" .,:")
            if clause:
                return _first_sentence(clause, limit=200)
    return None


def _acceptance(text: str) -> list[str]:
    low = _lower(text)
    for marker in ACCEPTANCE_CUES:
        idx = low.find(marker)
        if idx != -1:
            clause = text[idx + len(marker) :].strip(" :.,")
            if clause:
                return [_first_sentence(clause, limit=200)]
    return []


def _priority(text: str) -> str:
    low = _lower(text)
    if _contains_any(low, ("critical", "asap", "urgent", "must have", "high priority", "blocker")):
        return "high"
    if _contains_any(low, ("nice to have", "would be nice", "eventually", "later", "low priority", "someday")):
        return "low"
    return "unspecified"


def _is_injection(text: str) -> bool:
    return _contains_any(text, INJECTION_CUES) is not None


def _type_from_content(text: str, request_type: RequirementType | None) -> RequirementType:
    if request_type == "assumption":
        return "assumption"
    if _contains_any(text, INTEGRATION_CUES):
        return "integration"
    if _contains_any(text, CONSTRAINTS_ALL):
        return "constraint"
    if _contains_any(text, NONFUNCTIONAL_CUES):
        return "non_functional"
    return "functional"


CONSTRAINTS_ALL = CONSTRAINT_CUES


def _confidence_for(kind: StatementKind, type_: RequirementType, has_explicit_cue: bool) -> Indicator:
    if kind == "uncertain":
        return Indicator(level="low", score=0.3, basis="ambiguous or unresolved wording")
    if kind == "proposed_solution":
        return Indicator(level="low", score=0.4, basis="consultant proposal, not customer-agreed")
    if kind == "inferred":
        return Indicator(level="low", score=0.4, basis="inferred from context, not explicitly stated")
    # explicit
    if has_explicit_cue and type_ in {"functional", "integration", "non_functional", "constraint"}:
        return Indicator(level="high", score=0.8, basis="explicit customer requirement cue")
    return Indicator(level="medium", score=0.6, basis="stated by customer")


def _ref(transcript: Transcript, segment) -> SourceRef:
    return SourceRef(
        transcript_id=transcript.transcript_id,
        segment_id=segment.segment_id,
        speaker=segment.speaker,
        timestamp=segment.timestamp,
        quote=segment.text.strip(),
    )


def _make_requirement(
    *,
    transcript: Transcript,
    index: int,
    segment,
    description: str,
    type_: RequirementType,
    kind: StatementKind,
    confidence: Indicator,
    priority: str = "unspecified",
    rationale: str | None = None,
    dependencies: list[str] | None = None,
    risks: list[str] | None = None,
    acceptance: list[str] | None = None,
    extraction_status: str = "extracted",
) -> Requirement:
    rid = f"{transcript.transcript_id}-R{index:02d}"
    from app.schemas import Requirement as _R

    return _R(
        requirement_id=rid,
        project_id=transcript.project_id,
        transcript_id=transcript.transcript_id,
        description=description,
        requirement_type=type_,
        statement_kind=kind,
        priority=priority,
        rationale=rationale,
        dependencies=dependencies or [],
        risks=risks or [],
        acceptance_criteria=acceptance or [],
        source_refs=[_ref(transcript, segment)],
        confidence=confidence,
        status="needs_clarification" if kind == "uncertain" else "pending_review",
        scope="undecided",
        extraction_status=extraction_status,
        created_at=utcnow(),
        updated_at=utcnow(),
    )


# --- Rule-based extractor ----------------------------------------------------


class RuleBasedExtractor:
    """Deterministic cue-based requirement extractor."""

    def __init__(self, min_chars: int = 12) -> None:
        self.min_chars = min_chars

    def extract(self, transcript: Transcript) -> ExtractionResult:
        sides = _speaker_side(transcript)
        warnings: list[str] = []
        candidates: list[Requirement] = []
        index = 0
        seen_desc: set[str] = set()

        for segment in transcript.segments:
            text = segment.text.strip()
            if len(text) < self.min_chars:
                continue

            speaker_side = "other"
            if segment.speaker:
                speaker_side = sides.get(segment.speaker.lower(), "other")

            if _is_injection(text):
                warnings.append(
                    f"ignored untrusted instruction-like content in segment {segment.segment_id}"
                )
                continue

            is_question = text.rstrip().endswith("?")
            req_cue = _contains_any(text, REQUEST_CUES)
            open_cue = _contains_any(text, OPEN_QUESTION_CUES)
            assumption_cue = _contains_any(text, ASSUMPTION_CUES)
            solution_cue = _contains_any(text, PROPOSED_SOLUTION_CUES)
            pain_cue = _contains_any(text, PAIN_CUES)
            ambiguity_cue = _contains_any(text, AMBIGUITY_CUES)

            kind: StatementKind | None = None
            type_: RequirementType = "functional"

            if solution_cue and speaker_side == "consultant":
                kind = "proposed_solution"
                type_ = _type_from_content(text, None)
            elif assumption_cue:
                kind = "explicit"
                type_ = "assumption"
            elif open_cue or (is_question and not req_cue and speaker_side == "customer"):
                kind = "uncertain"
                type_ = "open_question"
            elif req_cue:
                kind = "explicit"
                type_ = _type_from_content(text, None)
            elif pain_cue and speaker_side == "customer":
                kind = "inferred"
                type_ = _type_from_content(text, None)
            elif ambiguity_cue and speaker_side == "customer":
                kind = "uncertain"
                type_ = "functional"

            if kind is None:
                continue

            description = _first_sentence(text)
            norm = re.sub(r"\W+", " ", description.lower()).strip()
            if norm in seen_desc:
                continue
            seen_desc.add(norm)

            index += 1
            confidence = _confidence_for(kind, type_, has_explicit_cue=bool(req_cue))
            deps: list[str] = []
            if _contains_any(text, DEPENDENCY_CUES):
                deps.append(_first_sentence(text, limit=160))
            risks: list[str] = []
            if _contains_any(text, RISK_CUES):
                risks.append(_first_sentence(text, limit=160))

            req = _make_requirement(
                transcript=transcript,
                index=index,
                segment=segment,
                description=description,
                type_=type_,
                kind=kind,
                confidence=confidence,
                priority=_priority(text),
                rationale=_rationale(text),
                dependencies=deps,
                risks=risks,
                acceptance=_acceptance(text),
                extraction_status="needs_review" if kind == "uncertain" else "extracted",
            )
            candidates.append(req)

        conflicts = detect_conflicts(candidates)
        for a, b, reason in conflicts:
            warnings.append(f"conflict between {a.requirement_id} and {b.requirement_id}: {reason}")

        return ExtractionResult(requirements=candidates, warnings=warnings)


# --- Conflict detection ------------------------------------------------------


def _number_topic(text: str) -> tuple[str | None, str | None]:
    """Return (magnitude, topic noun) for a scale-like statement, if any."""
    low = _lower(text)
    for match in _NUMBER_WORD_RE.finditer(low):
        raw = match.group(1).replace(",", "").strip()
        if raw.endswith("k"):
            raw = raw[:-1] + "000"
        try:
            value = str(int(raw))
        except ValueError:
            continue
        tail = low[match.end() : match.end() + 40]
        words = re.findall(r"[a-z]+", tail)
        for word in words:
            if word in {"members", "member", "users", "user", "listings", "listing", "records", "customers", "accounts"}:
                return value, word
    return None, None


def detect_conflicts(requirements: list[Requirement]) -> list[tuple[Requirement, Requirement, str]]:
    """Link contradictory statements; do not silently resolve them."""
    conflicts: list[tuple[Requirement, Requirement, str]] = []

    # Numeric conflicts on the same topic noun.
    by_topic: dict[str, list[tuple[str, Requirement]]] = {}
    for req in requirements:
        value, topic = _number_topic(req.description)
        if value and topic:
            by_topic.setdefault(topic, []).append((value, req))
    for topic, entries in by_topic.items():
        values = {v for v, _ in entries}
        if len(values) > 1:
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    if entries[i][0] != entries[j][0]:
                        a, b = entries[i][1], entries[j][1]
                        _link(a, b)
                        a.extraction_status = "needs_review"
                        b.extraction_status = "needs_review"
                        if a.status == "pending_review":
                            a.status = "needs_clarification"
                        if b.status == "pending_review":
                            b.status = "needs_clarification"
                        conflicts.append(
                            (a, b, f"conflicting {topic} scale ({entries[i][0]} vs {entries[j][0]})")
                        )

    # Polarity conflicts on integration/feature keywords.
    negators = (
        "not support",
        "not need",
        "no need",
        "do not need",
        "don't need",
        "don't want",
        "do not want",
        "not required",
        "no longer",
        "without",
        "disable",
        "remove",
        "can't",
        "cannot",
        "won't",
    )
    for i in range(len(requirements)):
        for j in range(i + 1, len(requirements)):
            a, b = requirements[i], requirements[j]
            for kw in INTEGRATION_CUES + ("newsletter", "multi-currency", "billing", "mobile app"):
                a_has = kw in _lower(a.description)
                b_has = kw in _lower(b.description)
                if not (a_has and b_has):
                    continue
                a_neg = _contains_any(a.description, negators) is not None
                b_neg = _contains_any(b.description, negators) is not None
                if a_neg != b_neg:
                    _link(a, b)
                    if a.status == "pending_review":
                        a.status = "needs_clarification"
                    if b.status == "pending_review":
                        b.status = "needs_clarification"
                    conflicts.append((a, b, f"conflicting statements about '{kw}'"))
                    break
    return conflicts


def _link(a: Requirement, b: Requirement) -> None:
    if b.requirement_id not in a.conflicts_with:
        a.conflicts_with.append(b.requirement_id)
    if a.requirement_id not in b.conflicts_with:
        b.conflicts_with.append(a.requirement_id)


# --- LLM extractor -----------------------------------------------------------


class LlmExtractor:
    """LLM-backed extractor; the chat provider is injected (mockable)."""

    def __init__(self, provider, *, system_prompt: str) -> None:
        self.provider = provider
        self.system_prompt = system_prompt

    def extract(self, transcript: Transcript) -> ExtractionResult:
        from app.prompt import build_extraction_user_prompt

        user_prompt = build_extraction_user_prompt(transcript)
        raw = self.provider.complete(self.system_prompt, user_prompt)
        return _parse_llm_requirements(raw, transcript)


_LLM_ALIASES = {
    "requirement_type": "requirement_type",
    "type": "requirement_type",
    "category": "requirement_type",
    "kind": "statement_kind",
    "statement_type": "statement_kind",
    "requirement": "description",
    "text": "description",
    "statement": "description",
    "source": "source_segment",
    "segment": "source_segment",
    "segment_id": "source_segment",
}


def _parse_llm_requirements(raw: str, transcript: Transcript) -> ExtractionResult:
    warnings: list[str] = []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # try to salvage a JSON array embedded in prose
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1 or end < start:
            return ExtractionResult(requirements=[], warnings=["llm output was not valid JSON"])
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return ExtractionResult(requirements=[], warnings=["llm output was not valid JSON"])

    if isinstance(data, dict):
        data = data.get("requirements", [])
    if not isinstance(data, list):
        return ExtractionResult(requirements=[], warnings=["llm output was not a list of requirements"])

    by_id = {seg.segment_id: seg for seg in transcript.segments}
    requirements: list[Requirement] = []
    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            warnings.append(f"skipped non-object requirement at index {i}")
            continue
        norm = {_LLM_ALIASES.get(k, k): v for k, v in item.items()}
        desc = str(norm.get("description", "")).strip()
        if not desc:
            warnings.append(f"skipped requirement {i} with empty description")
            continue
        type_ = str(norm.get("requirement_type", "functional")).strip().lower().replace(" ", "_")
        if type_ not in {"functional", "non_functional", "integration", "constraint", "assumption", "open_question"}:
            type_ = "functional"
        kind = str(norm.get("statement_kind", "explicit")).strip().lower().replace(" ", "_")
        if kind not in {"explicit", "inferred", "uncertain", "proposed_solution"}:
            kind = "explicit"
        seg_id = str(norm.get("source_segment", "")).strip()
        segment = by_id.get(seg_id)
        if segment is None:
            # fall back to a segment whose text contains the description
            segment = next(
                (s for s in transcript.segments if desc[:30].lower() in s.text.lower()),
                transcript.segments[0],
            )
            warnings.append(f"requirement {i} referenced unknown segment {seg_id!r}; linked to {segment.segment_id}")
        confidence = _confidence_for(kind, type_, has_explicit_cue=(kind == "explicit"))
        acs = norm.get("acceptance_criteria", [])
        if not isinstance(acs, list):
            acs = [str(acs)] if acs else []
        req = _make_requirement(
            transcript=transcript,
            index=i,
            segment=segment,
            description=_first_sentence(desc),
            type_=type_,
            kind=kind,
            confidence=confidence,
            priority=str(norm.get("priority", "unspecified")).lower() if norm.get("priority") else "unspecified",
            rationale=norm.get("rationale") if isinstance(norm.get("rationale"), str) else None,
            acceptance=[str(a) for a in acs],
            extraction_status="needs_review" if kind == "uncertain" else "extracted",
        )
        requirements.append(req)

    detect_conflicts(requirements)
    return ExtractionResult(requirements=requirements, warnings=warnings)


def build_extractor(settings: Settings):
    """Build the configured extractor (rules by default)."""
    if settings.extractor == "llm":
        from app.llm import build_chat_provider
        from app.prompt import EXTRACTION_SYSTEM_PROMPT

        provider = build_chat_provider(settings)
        return LlmExtractor(provider, system_prompt=EXTRACTION_SYSTEM_PROMPT)
    return RuleBasedExtractor()
