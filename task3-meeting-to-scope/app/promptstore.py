"""Versioned prompt store (schema: prompt/v1).

A prompt lives as a Markdown file ``prompts/<name>.vN.md`` whose front
matter block (between ``---`` fences) carries ``key: value`` pairs, and
``prompts/active.json`` maps prompt name -> active version. Loading
validates the manifest, the file, and the front matter, and raises
loudly on any problem so a run can never silently use wrong prompt text:

- ``PromptManifestError``  active.json missing / bad JSON / bad or absent entry
- ``PromptVersionMissing`` the active version's file does not exist
- ``PromptSchemaError``    front matter missing, malformed, schema mismatch,
  name/version/date mismatch, or empty body

Front matter keys required by ``prompt/v1``: name, version, schema,
date (YYYY-MM-DD), changelog. The body is everything after the closing
fence minus one trailing newline; ``sha256`` is over the UTF-8 bytes of
the LF-normalized body, so it is stable across platforms and checkouts.

Rollback: change the version number for the prompt in active.json (one
line) and restart. The same mechanism supports any future prompt-like
asset (e.g. edit-learning guidance): add its own ``<name>.vN.md``
file and its own key in active.json.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
ACTIVE_FILE = "active.json"
SCHEMA_ID = "prompt/v1"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED_KEYS = ("name", "version", "schema", "date", "changelog")


class PromptStoreError(RuntimeError):
    """Base class for prompt-store failures (all abort loudly)."""


class PromptManifestError(PromptStoreError):
    """active.json is missing, unparsable, or contains a bad entry."""


class PromptVersionMissing(PromptStoreError):
    """The active version's file does not exist."""


class PromptSchemaError(PromptStoreError):
    """Front matter is missing, malformed, or inconsistent with the manifest."""


@dataclass(frozen=True)
class LoadedPrompt:
    name: str
    version: int
    text: str
    sha256: str
    path: Path

    @property
    def ref(self) -> str:
        return f"{self.name}@v{self.version}"

    def report_block(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "sha256": self.sha256,
            "file": self.path.name,
        }


def load_prompt(name: str, *, prompts_dir: Path | None = None) -> LoadedPrompt:
    """Load the active version of ``name``; raises PromptStoreError on any fault."""
    directory = Path(prompts_dir) if prompts_dir else PROMPTS_DIR
    version = _read_manifest(directory, name)[name]
    path = directory / f"{name}.v{version}.md"
    if not path.is_file():
        raise PromptVersionMissing(
            f"prompt {name!r} active version {version} is missing: expected file {path}"
        )
    meta, body = _parse_prompt_file(path)
    _validate(meta, name=name, version=version, path=path)
    if not body:
        raise PromptSchemaError(f"prompt file {path} has an empty body")
    return LoadedPrompt(
        name=name, version=version, text=body,
        sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(), path=path,
    )


def _read_manifest(directory: Path, name: str) -> dict[str, int]:
    path = directory / ACTIVE_FILE
    if not path.is_file():
        raise PromptManifestError(f"prompt manifest missing: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PromptManifestError(f"prompt manifest is not valid JSON: {path}: {exc}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise PromptManifestError(f"prompt manifest is unreadable: {path}: {exc}") from exc
    if not isinstance(raw, dict) or not raw:
        raise PromptManifestError(
            f"prompt manifest must be a non-empty JSON object mapping name -> version: {path}"
        )
    manifest: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise PromptManifestError(
                f"prompt manifest entry {key!r} must map to a positive integer version: {path}"
            )
        manifest[key] = value
    if name not in manifest:
        raise PromptManifestError(
            f"prompt {name!r} has no entry in {path}; available: {', '.join(sorted(manifest))}"
        )
    return manifest


def _parse_prompt_file(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        raise PromptSchemaError(
            f"prompt file {path} must start with a '---' front matter fence"
        )
    try:
        fence = lines.index("---", 1)
    except ValueError:
        raise PromptSchemaError(
            f"prompt file {path} front matter is not closed with a '---' fence"
        ) from None
    meta: dict[str, str] = {}
    for line in lines[1:fence]:
        key, sep, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not sep or not key or not value:
            raise PromptSchemaError(
                f"front matter line {line!r} in {path} must be 'key: value'"
            )
        if key in meta:
            raise PromptSchemaError(f"duplicate front matter key {key!r} in {path}")
        meta[key] = value
    body = "\n".join(lines[fence + 1:])
    if body.endswith("\n"):
        body = body[:-1]
    return meta, body


def _validate(meta: dict[str, str], *, name: str, version: int, path: Path) -> None:
    missing = [key for key in REQUIRED_KEYS if key not in meta]
    if missing:
        raise PromptSchemaError(
            f"prompt file {path} front matter missing key(s): {', '.join(missing)}"
        )
    if meta["name"] != name:
        raise PromptSchemaError(
            f"front matter name {meta['name']!r} does not match prompt {name!r}: {path}"
        )
    if meta["schema"] != SCHEMA_ID:
        raise PromptSchemaError(
            f"schema mismatch in {path}: expected {SCHEMA_ID!r}, got {meta['schema']!r}"
        )
    try:
        file_version = int(meta["version"])
    except ValueError:
        raise PromptSchemaError(
            f"front matter version {meta['version']!r} in {path} is not an integer"
        ) from None
    if file_version != version:
        raise PromptSchemaError(
            f"front matter version {file_version} does not match active version "
            f"{version} for {name!r}: {path}"
        )
    if not DATE_RE.match(meta["date"]):
        raise PromptSchemaError(
            f"front matter date {meta['date']!r} in {path} must be YYYY-MM-DD"
        )
