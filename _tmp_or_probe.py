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

req = urllib.request.Request("https://openrouter.ai/api/v1/credits", headers={"Authorization": "Bearer " + key})
try:
    print("credits:", urllib.request.urlopen(req, timeout=20).read().decode()[:500])
except urllib.error.HTTPError as e:
    print("credits HTTP", e.code, e.read().decode()[:300])

body = json.dumps({"model": "anthropic/claude-haiku-4.5", "messages": [{"role": "user", "content": "say ok"}], "max_tokens": 5}).encode()
req2 = urllib.request.Request(
    "https://openrouter.ai/api/v1/chat/completions",
    data=body,
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
)
try:
    r = urllib.request.urlopen(req2, timeout=30)
    print("chat HTTP", r.status, r.read().decode()[:400])
except urllib.error.HTTPError as e:
    print("chat HTTP", e.code, e.read().decode()[:400])
