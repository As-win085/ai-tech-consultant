const { v4: uuidv4 } = require('uuid');

function buildDraft(email, classification, kbResp) {
  const citations = Array.isArray(kbResp.citations) ? kbResp.citations : [];
  let body;
  if (kbResp.evidence_status === 'sufficient' && citations.length > 0) {
    const lines = [
      `Subject: Re: ${email.subject}`,
      `Hi ${email.from.split('@')[0] || 'there'},`,
      '',
      kbResp.answer,
      '',
      'Sources (from Knowledge Brain):',
      ...citations.map((c, i) => `- [${i + 1}] ${c.title || c.article_id || 'Source'}${c.canonical_url ? ' — ' + c.canonical_url : ''}${c.chunk_id ? ` (chunk:${c.chunk_id})` : ''}`),
      '',
      'If this doesn’t answer your question, could you share a few more details?',
      '',
      'Regards,',
      'Support Team',
    ];
    body = lines.join('\n');
  } else {
    body = `Subject: Re: ${email.subject}\nHi ${email.from.split('@')[0] || 'there'},\n\nWe need a bit more information to answer this accurately.\n\nIf you can describe the exact issue (steps, error messages, account/email), we'll help right away.\n\nRegards,\nSupport Team`;
  }

  return {
    id: uuidv4(),
    emailId: email.id,
    body,
    grounded: kbResp.evidence_status === 'sufficient' && citations.length > 0,
    citations,
    kbRequestId: kbResp.request_id || null,
    kbEvidenceStatus: kbResp.evidence_status || null,
    kbNeedsEscalation: !!kbResp.needs_escalation,
    createdAt: new Date().toISOString(),
    notes: null,
  };
}

module.exports = { buildDraft };
