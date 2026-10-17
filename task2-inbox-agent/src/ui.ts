export const reviewUiHtml = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>SupportFlow Inbox Agent — Review</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #f5f6f8; color: #1b1f24; }
  header { background: #1f2d3d; color: #fff; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; }
  header h1 { font-size: 16px; margin: 0; }
  #stats { font-size: 12px; opacity: 0.9; }
  main { display: grid; grid-template-columns: 340px 1fr; gap: 16px; padding: 16px; }
  .panel { background: #fff; border: 1px solid #e1e4e8; border-radius: 6px; overflow: hidden; }
  .panel h2 { font-size: 13px; margin: 0; padding: 10px 12px; background: #eef1f4; border-bottom: 1px solid #e1e4e8; }
  #queue { max-height: 80vh; overflow-y: auto; }
  .qitem { padding: 10px 12px; border-bottom: 1px solid #eef1f4; cursor: pointer; }
  .qitem:hover { background: #f0f6ff; }
  .qitem.active { background: #e3f0ff; }
  .qitem .subj { font-weight: 600; font-size: 13px; }
  .qitem .meta { font-size: 11px; color: #6a737d; margin-top: 2px; }
  .badge { display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 10px; background: #dfe6ed; margin-right: 4px; }
  .badge.risk { background: #ffdce0; color: #86181d; }
  #detail { padding: 14px 16px; }
  #detail h3 { margin: 0 0 4px; font-size: 15px; }
  .kv { font-size: 12px; color: #444d56; margin-bottom: 10px; }
  pre { background: #f6f8fa; border: 1px solid #e1e4e8; padding: 10px; border-radius: 4px; white-space: pre-wrap; font-size: 12px; }
  textarea { width: 100%; min-height: 180px; font-family: ui-monospace, monospace; font-size: 12px; padding: 8px; box-sizing: border-box; }
  .actions { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
  button { padding: 7px 14px; border-radius: 4px; border: 1px solid #d1d5da; background: #fff; cursor: pointer; font-size: 13px; }
  button.primary { background: #2ea44f; color: #fff; border-color: #2c974b; }
  button.danger { background: #d73a49; color: #fff; border-color: #cb2431; }
  button.warn { background: #f9a825; color: #1b1f24; border-color: #e09600; }
  .citations { margin-top: 10px; font-size: 12px; }
  .citations li { margin-bottom: 3px; }
  #msg { margin-left: 10px; font-size: 12px; color: #2ea44f; }
  .empty { padding: 20px; color: #6a737d; font-size: 13px; }
</style>
</head>
<body>
<header>
  <h1>SupportFlow Inbox Agent — Human Review</h1>
  <div id="stats">loading…</div>
</header>
<main>
  <div class="panel">
    <h2>Queue</h2>
    <div id="queue"></div>
  </div>
  <div class="panel">
    <h2>Review</h2>
    <div id="detail"><div class="empty">Select an email from the queue.</div></div>
  </div>
</main>
<script>
const api = (p, o) => fetch(p, o).then(r => r.json());
let current = null;
let items = [];

function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

async function refresh(){
  const [list, stats] = await Promise.all([api('/emails'), api('/stats')]);
  items = list.items;
  document.getElementById('stats').textContent =
    'consecutive unedited approvals: ' + stats.automation.consecutiveUneditedApprovals +
    ' / ' + stats.automation.threshold +
    (stats.automation.automationEligible ? ' — AUTOMATION-ELIGIBLE (review still required)' : '');
  const q = document.getElementById('queue');
  q.innerHTML = items.length ? '' : '<div class="empty">No emails ingest yet.</div>';
  for (const it of items){
    const div = document.createElement('div');
    div.className = 'qitem' + (current && current.id===it.id ? ' active':'');
    const risks = (it.classification.riskFlags||[]).map(r=>'<span class="badge risk">'+esc(r)+'</span>').join('');
    div.innerHTML = '<div class="subj">'+esc(it.email.subject)+'</div>' +
      '<div class="meta">'+esc(it.classification.category)+' · '+esc(it.classification.urgency)+' · '+esc(it.state)+'</div>' +
      '<div class="meta">'+risks+'</div>';
    div.onclick = ()=>select(it.id);
    q.appendChild(div);
  }
}

async function select(id){
  const it = await api('/emails/'+id);
  current = it;
  render();
  refresh();
}

function render(){
  const it = current;
  if (!it) return;
  const d = it.draft;
  const risks = (it.classification.riskFlags||[]).map(r=>'<span class="badge risk">'+esc(r)+'</span>').join('');
  const cites = d && d.citations ? d.citations.map((c,i)=>'<li>['+(i+1)+'] '+esc(c.title||c.article_id||'source')+' — '+esc(c.canonical_url||'')+' <code>'+esc(c.chunk_id)+'</code></li>').join('') : '';
  document.getElementById('detail').innerHTML =
    '<h3>'+esc(it.email.subject)+'</h3>' +
    '<div class="kv">from '+esc(it.email.from)+' · state: <b>'+esc(it.state)+'</b> · category: '+esc(it.classification.category)+' · urgency: '+esc(it.classification.urgency)+' · confidence: '+esc(it.classification.confidence)+'</div>' +
    '<div class="kv">'+risks+(it.automationExcluded?'<span class="badge">automation-excluded: '+esc((it.automationExclusionReasons||[]).join('; '))+'</span>':'')+'</div>' +
    '<div class="kv"><b>Customer email</b></div><pre>'+esc(it.email.body)+'</pre>' +
    '<div class="kv"><b>Draft response</b> '+(d?('('+(d.grounded?'grounded':'not grounded')+')'):'(none)')+'</div>' +
    (d ? '<textarea id="draftbox">'+esc(d.body)+'</textarea>' +
      '<div class="citations"><b>Internal citations</b><ul>'+cites+'</ul></div>'
       : '<div class="empty">No draft yet. Generate one to pull grounded evidence from the Knowledge Brain.</div>') +
    '<div class="actions">' +
      (d ? '' : '<button class="primary" onclick="genDraft()">Generate draft</button>') +
      (d && it.state==='pending_review' ? (
        '<button class="primary" onclick="act(\\'edit\\')">Save edits + approve</button>' +
        '<button onclick="act(\\'approve\\')">Approve as-is</button>' +
        '<button class="danger" onclick="act(\\'reject\\')">Reject</button>' +
        '<button class="warn" onclick="act(\\'escalate\\')">Escalate</button>'
      ) : (d ? '<span class="kv">Resolved ('+esc(it.state)+'). No further action allowed.</span>' : '')) +
      '<span id="msg"></span>' +
    '</div>';
}

async function genDraft(){
  await api('/emails/'+current.id+'/draft', {method:'POST'});
  await select(current.id);
}
async function act(action){
  const body = { action };
  if (action==='edit'){ body.editedDraft = document.getElementById('draftbox').value; }
  if (action==='reject'){ body.rejectionReason = prompt('Rejection reason (for feedback records):') || ''; }
  if (action==='escalate'){ body.escalationReason = prompt('Escalation reason:') || ''; }
  const res = await fetch('/emails/'+current.id+'/review', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(body)});
  const data = await res.json();
  if (!res.ok){ alert('Review failed: '+(data.error&&data.error.message||res.status)); return; }
  const msg = document.getElementById('msg'); if (msg) msg.textContent = 'saved';
  await select(current.id);
}

refresh();
</script>
</body>
</html>`;
