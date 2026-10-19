import json
import os
import urllib.error
import urllib.request
from pathlib import Path

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
    return raw.split("---\n", 2)[2]


cases = [
    ("v1@2048", body_of("task3-meeting-to-scope/prompts/extraction_system.v1.md"), 2048),
    ("v2@2048", body_of("task3-meeting-to-scope/prompts/extraction_system.v2.md"), 2048),
    ("v2@1024", body_of("task3-meeting-to-scope/prompts/extraction_system.v2.md"), 1024),
    ("v1@1024", body_of("task3-meeting-to-scope/prompts/extraction_system.v1.md"), 1024),
]

user = "Meeting transcript: Sam will send the invoice on Friday. Dana owns the migration."
for label, system, max_tokens in cases:
    payload = json.dumps({
        "model": "anthropic/claude-haiku-4.5",
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
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
        u = resp.get("usage", {})
        print(label, "HTTP", r.status, "billed_cost", u.get("cost"))
    except urllib.error.HTTPError as e:
        print(label, "HTTP", e.code, e.read().decode()[:300])
