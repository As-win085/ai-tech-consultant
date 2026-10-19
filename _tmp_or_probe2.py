import json
import urllib.error
import urllib.request
from pathlib import Path

key = None
import os
key = os.environ.get("OPENROUTER_API_KEY", "").strip()
if not key:
    for f in (Path("task1-knowledge-brain/.env"), Path("task2-inbox-agent/.env")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("OPENROUTER_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    key = value
                    break
        if key:
            break


def body_of(path: str) -> str:
    raw = Path(path).read_text(encoding="utf-8")
    parts = raw.split("---\n", 2)
    return parts[2]


v1 = body_of("task3-meeting-to-scope/prompts/extraction_system.v1.md")
v2 = body_of("task3-meeting-to-scope/prompts/extraction_system.v2.md")
print("v1 chars", len(v1), "v2 chars", len(v2))

for label, system in (("v1", v1), ("v2", v2)):
    payload = json.dumps({
        "model": "anthropic/claude-haiku-4.5",
        "max_tokens": 300,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": "Meeting: Sam will send the invoice Friday."},
        ],
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        r = urllib.request.urlopen(req, timeout=45)
        resp = json.loads(r.read().decode())
        print(label, "HTTP", r.status, "tokens", resp.get("usage"))
    except urllib.error.HTTPError as e:
        print(label, "HTTP", e.code, e.read().decode()[:400])
