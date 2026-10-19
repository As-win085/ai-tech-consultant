import urllib.request, json

BASE = 'https://lvcmaxrolaolxiqyabsk.supabase.co'
KEY = 'sb_publishable_ilo2kEXsdk8cEO7Z1DruHg_zJFLuIlJ'
H = {
    'apikey': KEY,
    'Authorization': 'Bearer ' + KEY,
    'Content-Type': 'application/json'
}

def rpc(sql):
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(f'{BASE}/rest/v1/rpc/exec_sql', data=body, headers=H, method='POST')
    try:
        res = urllib.request.urlopen(req, timeout=10)
        return json.loads(res.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode()

# Check all tables across all schemas
sql = """
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('public','inbox_agent','meeting_to_scope')
ORDER BY table_schema, table_name
"""
data, err = rpc(sql)
if err:
    print('RPC not available:', err[:120])
else:
    for row in data:
        print(f"  {row['table_schema']:<20} {row['table_name']}")
