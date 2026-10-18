"""Small dependency-free Knowledge Chat page served by FastAPI."""

CHAT_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Knowledge Chat</title><style>
body{font:16px system-ui,sans-serif;max-width:850px;margin:3rem auto;padding:0 1rem;color:#172033;background:#f7f8fb}
main{background:#fff;padding:2rem;border:1px solid #dce1eb;border-radius:14px;box-shadow:0 8px 32px #10204012}
h1{margin-top:0}label{display:block;font-weight:600;margin:.8rem 0 .4rem}textarea{width:100%;min-height:110px;padding:.8rem;border:1px solid #bbc5d5;border-radius:8px;font:inherit;box-sizing:border-box}
button{margin-top:1rem;background:#1b4db1;color:white;border:0;border-radius:7px;padding:.65rem 1rem;font:inherit;cursor:pointer}#result{margin-top:1.5rem;white-space:pre-wrap}.state{font-weight:700}.citation{margin:.5rem 0}.muted{color:#596579}
</style></head><body><main><h1>Knowledge Chat</h1><p class="muted">Answers use the indexed support knowledge base. If evidence is missing, the service abstains.</p>
<form id="ask"><label for="question">Question</label><textarea id="question" required maxlength="2000" placeholder="How do I reset a member password?"></textarea><button>Ask Knowledge Brain</button></form>
<section id="result" aria-live="polite"></section></main><script>
const form=document.querySelector('#ask'), result=document.querySelector('#result');
form.addEventListener('submit',async e=>{e.preventDefault();result.textContent='Checking the knowledge base…';try{
const response=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:document.querySelector('#question').value})});
const data=await response.json();if(response.status===503){result.innerHTML='<p class="state">Service unavailable</p><p>The Knowledge Brain dependency is unavailable. No answer was generated.</p>';return}
if(!response.ok){result.textContent=data.error?.message||'The request could not be processed.';return}
result.replaceChildren();const state=document.createElement('p');state.className='state';state.textContent=data.evidence_status==='sufficient'?'Evidence found':(data.evidence_status==='unavailable'?'Evidence service unavailable':'Insufficient evidence — abstained');result.append(state);
const answer=document.createElement('p');answer.textContent=data.answer;result.append(answer);
if(data.citations?.length){const h=document.createElement('h2');h.textContent='Citations';result.append(h);for(const c of data.citations){const p=document.createElement('p');p.className='citation';const label=`${c.title||c.article_id}${c.heading?' — '+c.heading:''}`;try{const url=new URL(c.canonical_url||'');if(url.protocol==='https:'||url.protocol==='http:'){const a=document.createElement('a');a.href=url.href;a.textContent=label;p.append(a)}else{p.textContent=label}}catch(_){p.textContent=label}result.append(p)}}
if(data.needs_escalation){const p=document.createElement('p');p.className='state';p.textContent=`Escalation required${data.escalation_id?' (reference '+data.escalation_id+')':''}`;result.append(p)}
}catch(_){result.textContent='Service unavailable. The request did not produce a Knowledge Brain answer.'}});
</script></body></html>"""
