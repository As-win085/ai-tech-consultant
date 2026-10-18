"""Minimal server-rendered UI for human review.

A single HTML page (no build step) that talks to the JSON API: ingest a transcript,
inspect extracted requirements, run feasibility, generate a proposal, and
approve/reject requirements. Intended for local demonstration and manual review.
"""

from __future__ import annotations

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Meeting-to-Scope Agent</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 1.5rem; background:#0f1115; color:#e6e6e6; }
  h1 { font-size: 1.3rem; } h2 { font-size: 1.05rem; margin-top: 1.5rem; }
  input, textarea, button { font: inherit; }
  textarea { width: 100%; min-height: 9rem; background:#161a21; color:#e6e6e6; border:1px solid #2a2f3a; border-radius:6px; padding:.6rem; }
  input { background:#161a21; color:#e6e6e6; border:1px solid #2a2f3a; border-radius:6px; padding:.5rem; }
  button { background:#3b82f6; color:white; border:0; border-radius:6px; padding:.5rem .9rem; cursor:pointer; margin-right:.4rem; }
  button.secondary { background:#374151; } button.danger { background:#b91c1c; }
  .row { display:flex; gap:.5rem; flex-wrap:wrap; align-items:center; margin:.6rem 0; }
  table { width:100%; border-collapse:collapse; margin-top:.6rem; }
  th,td { text-align:left; border-bottom:1px solid #2a2f3a; padding:.4rem; font-size:.85rem; vertical-align:top; }
  .tag { display:inline-block; padding:.05rem .4rem; border-radius:4px; font-size:.72rem; background:#1f2937; }
  .status-approved{color:#4ade80}.status-rejected{color:#f87171}.status-needs_clarification{color:#fbbf24}
  pre { background:#161a21; padding:.6rem; border-radius:6px; overflow:auto; font-size:.78rem; }
  .muted { color:#9ca3af; font-size:.8rem; }
</style>
</head>
<body>
<h1>Meeting-to-Scope Agent</h1>
<p class="muted">Feed a synthetic transcript, review extracted requirements, assess feasibility, and generate a draft proposal. Source references link every requirement to a transcript segment.</p>

<div class="row">
  <label>Project ID <input id="projectId" value="brightpath-directory" /></label>
  <label>Transcript ID <input id="transcriptId" value="mtg-001-kickoff" /></label>
  <label><input type="checkbox" id="asJson" /> input is JSON</label>
</div>
<textarea id="transcriptText">Dana [00:00:30]: We need to support up to 50,000 members without the site slowing down.
Dana [00:02:00]: We also need single sign-on for enterprise clients.
Sam [00:03:00]: We could add a caching layer.
Dana [00:04:00]: We'd like a more modern mobile experience but we are not sure yet what that means.</textarea>
<div class="row">
  <button onclick="ingest()">Ingest transcript</button>
  <button class="secondary" onclick="loadRequirements()">Load requirements</button>
  <button class="secondary" onclick="assess()">Assess feasibility</button>
  <button class="secondary" onclick="propose()">Generate proposal</button>
  <button class="secondary" onclick="loadBaselines()">Load baselines</button>
</div>
<p id="msg" class="muted"></p>

<h2>Requirements</h2>
<table id="reqTable"><thead><tr><th>ID</th><th>Type</th><th>Kind</th><th>Description</th><th>Source</th><th>Status</th><th>Actions</th></tr></thead><tbody></tbody></table>

<h2>Feasibility</h2>
<table id="feasTable"><thead><tr><th>Requirement</th><th>Status</th><th>Basis</th></tr></thead><tbody></tbody></table>

<h2>Proposal</h2>
<pre id="proposalBox">(none yet)</pre>

<h2>Baselines</h2>
<pre id="baselineBox">(none yet)</pre>

<script>
const $ = (id) => document.getElementById(id);
function msg(t){ $("msg").textContent = t; }
function esc(s){ return (s??"").toString().replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
function pid(){ return $("projectId").value.trim(); }

async function api(method, path, body){
  const res = await fetch(path, {method, headers:{"Content-Type":"application/json"}, body: body?JSON.stringify(body):undefined});
  const text = await res.text();
  let data; try { data = text?JSON.parse(text):{}; } catch(e){ data = {raw:text}; }
  if(!res.ok){ throw new Error((data.error&&data.error.message)||("HTTP "+res.status)); }
  if(data.error) throw new Error(data.error.message);
  return data;
}

function transcriptPayload(){
  const p = pid(), tid = $("transcriptId").value.trim();
  if($("asJson").checked){ const obj = JSON.parse($("transcriptText").value); return obj; }
  return {project_id:p, transcript_id:tid, text:$("transcriptText").value,
          participants:[{"name":"Dana","side":"customer"},{"name":"Sam","side":"consultant"}]};
}

async function ingest(){
  try{ msg("ingesting..."); const data = await api("POST","/transcripts",transcriptPayload());
    msg("ingested " + data.transcript.transcript_id + " (" + data.requirements.length + " requirements" + (data.idempotent?", idempotent":"") + ")");
    renderRequirements(data.requirements);
  }catch(e){ msg("error: "+e.message); }
}
async function loadRequirements(){
  try{ const reqs = await api("GET",`/projects/${encodeURIComponent(pid())}/requirements`); renderRequirements(reqs); msg(reqs.length+" requirements"); }
  catch(e){ msg("error: "+e.message); }
}
function renderRequirements(reqs){
  const tb = $("reqTable").querySelector("tbody"); tb.innerHTML="";
  for(const r of reqs){
    const src = (r.source_refs&&r.source_refs[0]) ? (r.source_refs[0].speaker||"")+" @"+(r.source_refs[0].timestamp||"")+" ["+r.source_refs[0].segment_id+"]" : "";
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${esc(r.requirement_id)}</td><td><span class="tag">${esc(r.requirement_type)}</span></td>
      <td>${esc(r.statement_kind)}</td><td>${esc(r.description)}</td><td class="muted">${esc(src)}</td>
      <td class="status-${esc(r.status)}">${esc(r.status)}</td>`;
    const actions = document.createElement("td");
    for(const [label,status,cls] of [["Approve","approved",""],["Reject","rejected","danger"],["Clarify","needs_clarification","secondary"]]){
      const b=document.createElement("button"); b.textContent=label; b.className=cls;
      b.onclick=()=>reviewReq(r.requirement_id,status); actions.appendChild(b);
    }
    tr.appendChild(actions); tb.appendChild(tr);
  }
}
async function reviewReq(rid,status){
  try{ await api("POST",`/requirements/${encodeURIComponent(rid)}/review`,{to_status:status,actor:"ui",reason:status==="approved"?null:"via UI"});
    await loadRequirements();
  }catch(e){ msg("error: "+e.message); }
}
async function assess(){
  try{ const data = await api("POST",`/projects/${encodeURIComponent(pid())}/feasibility`,{}); const tb=$("feasTable").querySelector("tbody"); tb.innerHTML="";
    for(const [rid,a] of Object.entries(data)){ const tr=document.createElement("tr");
      tr.innerHTML=`<td>${esc(rid)}</td><td>${esc(a.status)}</td><td class="muted">${esc(a.basis)}</td>`; tb.appendChild(tr); }
    msg("feasibility assessed");
  }catch(e){ msg("error: "+e.message); }
}
async function propose(){
  try{ const p = await api("POST",`/projects/${encodeURIComponent(pid())}/proposals`,{}); $("proposalBox").textContent = JSON.stringify(p,null,2); msg("proposal "+p.proposal_id); }
  catch(e){ msg("error: "+e.message); }
}
async function loadBaselines(){
  try{ const b = await api("GET",`/projects/${encodeURIComponent(pid())}/baselines`); $("baselineBox").textContent = JSON.stringify(b,null,2); }
  catch(e){ msg("error: "+e.message); }
}
</script>
</body>
</html>
"""


def get_ui_html() -> str:
    return _PAGE
