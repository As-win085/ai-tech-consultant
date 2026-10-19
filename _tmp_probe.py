"""Status-only probe of Gemini batchEmbedContents with the app's real key/endpoint."""
import json
import urllib.request
import urllib.error

key = None
for line in open('task1-knowledge-brain/.env', encoding='utf-8'):
    line = line.strip()
    if line.startswith('EMBEDDING_API_KEY='):
        key = line.partition('=')[2].strip().strip('"').strip("'")
if not key:
    print('EMBEDDING_API_KEY not found')
    raise SystemExit(1)

url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents'
body = json.dumps({'requests': [{'model': 'models/gemini-embedding-001',
                                 'content': {'parts': [{'text': 'probe'}]},
                                 'outputDimensionality': 768}]}).encode()
req = urllib.request.Request(url, data=body,
                             headers={'content-type': 'application/json', 'x-goog-api-key': key},
                             method='POST')
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        print('gemini batchEmbedContents: HTTP', r.status, '(quota OK)')
except urllib.error.HTTPError as e:
    print('gemini batchEmbedContents: HTTP', e.code, 'Retry-After:', e.headers.get('Retry-After'))
    print('  body:', e.read().decode('utf-8', 'replace')[:300])
except Exception as e:
    print('gemini batchEmbedContents: ERROR', type(e).__name__, str(e)[:200])
