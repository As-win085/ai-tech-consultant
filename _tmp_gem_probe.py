import json
import os
import urllib.error
import urllib.request
from pathlib import Path

key = None
for env_file in (Path("task1-knowledge-brain/.env"), Path("task3-meeting-to-scope/.env")):
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("EMBEDDING_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                key = value
                break
    if key:
        break
if not key:
    key = os.environ.get("EMBEDDING_API_KEY", "").strip()

body = json.dumps({
    "model": "gemini-3.8-flash",
    "contents": [{"role": "user", "parts": [{"text": "say ok"}]}],
    "generationConfig": {"maxOutputTokens": 16},
}).encode()
req = urllib.request.Request(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
    data=body,
    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
)
try:
    r = urllib.request.urlopen(req, timeout=30)
    resp = json.loads(r.read().decode())
    print("gemini HTTP", r.status, "text:", resp["candidates"][0]["content"]["parts"][0]["text"][:50], "usage:", resp.get("usageMetadata"))
except urllib.error.HTTPError as e:
    print(e.read().decode())
