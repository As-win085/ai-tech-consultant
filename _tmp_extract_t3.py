"""One-off: extract T3 prompts into the versioned store (byte-identical v1 + real v2)."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, 'task3-meeting-to-scope')
from app.prompt import EXTRACTION_SYSTEM_PROMPT as p  # noqa: E402 (pre-edit import)

root = Path('task3-meeting-to-scope/prompts')
root.mkdir(exist_ok=True)

sha1 = hashlib.sha256(p.encode('utf-8')).hexdigest()

RULE7 = (
    "7. If the same requirement is repeated across segments (identical wording or an "
    "obvious restatement of the same request), emit it ONCE and set source_segment to "
    "the first segment where it appears. This does not override rule 6: genuinely "
    "different or contradictory statements are not repetitions - keep both."
)
v2 = p + "\n" + RULE7
sha2 = hashlib.sha256(v2.encode('utf-8')).hexdigest()


def write_prompt(name, version, changelog, body):
    fm = (
        "---\n"
        f"name: {name}\n"
        f"version: {version}\n"
        "schema: prompt/v1\n"
        "date: 2026-10-19\n"
        f"changelog: {changelog}\n"
        "---\n"
    )
    path = root / f"{name}.v{version}.md"
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(fm + body + "\n")
    return path


p1 = write_prompt('extraction_system', 1,
                  f'byte-identical extraction of EXTRACTION_SYSTEM_PROMPT from task3 app/prompt.py (body sha256 {sha1})',
                  p)
p2 = write_prompt('extraction_system', 2,
                  f'adds rule 7: repeated statements emitted once, first segment kept; contradictions still kept per rule 6; fixes tuning case duplicate-11 (body sha256 {sha2})',
                  v2)
(root / 'active.json').write_text(json.dumps({'extraction_system': 1}, indent=2) + '\n', encoding='utf-8')

print('v1', p1.name, 'sha', sha1, 'chars', len(p))
print('v2', p2.name, 'sha', sha2, 'chars', len(v2))

# verify round-trip through the new loader: v1 body must equal the original exactly
from app.promptstore import load_prompt  # noqa: E402
got = load_prompt('extraction_system', prompts_dir=root)
assert got.version == 1 and got.text == p, 'v1 NOT byte-identical'
assert got.sha256 == sha1
print('loader round-trip OK: v1 text == original constant')
