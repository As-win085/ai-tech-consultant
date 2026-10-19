import json
import os
import urllib.error
import urllib.request
from pathlib import Path

key = os.environ.get("GROQ_API_KEY", "").strip()
if not key:
    for env_file in (Path("task1-knowledge-brain/.env"), Path("task2-inbox-agent/.env")):
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GROQ_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    key = value
                    break
        if key:
            break

payload = json.dumps({
    "model": "llama-3.3-70b-versatile",
    "max_tokens": 2048,
    "temperature": 0,
    "messages": [
        {"role": "system", "content": "Reply with a single JSON object only."},
        {"role": "user", "content": '{"ok": '},
    ],
}).encode()
req = urllib.request.Request(
    "https://api.groq.com/openai/v1/chat/completions",
    data=payload,
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
)
try:
    r = urllib.request.urlopen(req, timeout=30)
    resp = json.loads(r.read().decode())
    print("groq HTTP", r.status, "model:", resp.get("model"), "usage:", resp.get("usage"))
except urllib.error.HTTPError as e:
    print("groq HTTP", e.code, e.read().decode()[:400])
