import { v4 as uuidv4 } from 'uuid';
import { Citation, Draft, Email, KbAnswer } from './types';

const SIGN_OFF = ['', 'Regards,', 'SupportFLow Support Team'];

function isGrounded(kb: KbAnswer): boolean {
  return kb.evidence_status === 'sufficient' && Array.isArray(kb.citations) && kb.citations.length > 0;
}

function displayName(from: string): string {
  const local = from.split('@')[0] ?? 'there';
  return local.replace(/[._-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function buildDraft(email: Email, kb: KbAnswer): Draft {
  const grounded = isGrounded(kb);
  const citations: Citation[] = Array.isArray(kb.citations) ? kb.citations : [];

  let body: string;
  let confirmedFacts: string[] = [];
  let assumptions: string[] = [];
  let escalationReason: string | null = null;

  if (grounded) {
    confirmedFacts = [kb.answer.trim()];
    body = [
      `Subject: Re: ${email.subject}`,
      '',
      `Hi ${displayName(email.from)},`,
      '',
      'Thanks for reaching out. Here is what we can confirm from our product documentation:',
      '',
      kb.answer.trim(),
      '',
    ].join('\n');
    body += '\n' + SIGN_OFF.join('\n');
  } else {
    escalationReason =
      kb.escalation_reason?.trim() ||
      `Insufficient evidence (status: ${kb.evidence_status}); human review required before replying.`;
    assumptions = ['The customer may need a clarification question or a human specialist response.'];
    body = [
      `Subject: Re: ${email.subject}`,
      '',
      `Hi ${displayName(email.from)},`,
      '',
      'Thanks for your message. To make sure we give you an accurate answer, we need to look into this a little further and will follow up shortly.',
      '',
      'In the meantime, could you confirm any relevant details (exact steps, screen, account, or error message)?',
      '',
      ...SIGN_OFF,
    ].join('\n');
  }

  return {
    id: uuidv4(),
    emailId: email.id,
    body,
    grounded,
    citations,
    confirmedFacts,
    assumptions,
    escalationReason,
    kbRequestId: kb.request_id,
    kbEvidenceStatus: kb.evidence_status,
    kbNeedsEscalation: !!kb.needs_escalation,
    createdAt: new Date().toISOString(),
  };
}

export function renderInternalReferences(draft: Draft): string[] {
  return draft.citations.map(
    (c, i) => `[${i + 1}] ${c.title ?? c.article_id ?? 'Source'}${c.canonical_url ? ` — ${c.canonical_url}` : ''} (chunk:${c.chunk_id})`,
  );
}
