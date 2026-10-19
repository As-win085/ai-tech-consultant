import urllib.request, json

BASE = 'https://lvcmaxrolaolxiqyabsk.supabase.co/rest/v1'
KEY = 'sb_publishable_ilo2kEXsdk8cEO7Z1DruHg_zJFLuIlJ'
H = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY}

def check(label, tables, schema_header=None):
    print(f'\n=== {label} ===')
    headers = dict(H)
    if schema_header:
        headers['Accept-Profile'] = schema_header
    all_ok = True
    for t in tables:
        try:
            req = urllib.request.Request(f'{BASE}/{t}?select=count', headers=headers)
            res = urllib.request.urlopen(req, timeout=10)
            count = json.loads(res.read().decode())[0]['count']
            print(f'  OK      {t:<35} rows={count}')
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:100]
            print(f'  MISSING {t:<35} HTTP {e.code} {body}')
            all_ok = False
        except Exception as e:
            print(f'  ERROR   {t:<35} {e}')
            all_ok = False
    return all_ok

t1 = check('Task 1 — Knowledge Brain (public)', [
    'articles', 'chunks', 'chunk_embeddings', 'indexing_runs',
    'escalations', 'escalation_answers', 'ingestion_runs', 'schema_migrations'
])

t2 = check('Task 2 — Inbox Agent (inbox_agent)', [
    'inbox_items', 'audit_log', 'feedback', 'agent_state', 'schema_migrations'
], schema_header='inbox_agent')

t3 = check('Task 3 — Meeting-to-Scope (meeting_to_scope)', [
    'mt_project', 'mt_transcript', 'mt_requirement', 'mt_assessment',
    'mt_proposal', 'mt_baseline', 'mt_change_summary', 'mt_baseline_update',
    'mt_review_event', 'schema_migrations'
], schema_header='meeting_to_scope')

print('\n=== SUMMARY ===')
print('Task 1:', 'PASS' if t1 else 'FAIL - some tables missing')
print('Task 2:', 'PASS' if t2 else 'FAIL - inbox_agent schema may not be exposed in Supabase API settings')
print('Task 3:', 'PASS' if t3 else 'FAIL - meeting_to_scope schema may not be exposed in Supabase API settings')
