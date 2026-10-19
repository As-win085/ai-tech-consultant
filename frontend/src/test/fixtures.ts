import type { AskResponse } from '@/types/knowledge';
import type { InboxItem, ReviewResultResponse, StatsResponse, InboxReadyResponse } from '@/types/inbox';
import type { IngestResponse, Requirement, FeasibilityAssessment, ChangeSummary, Proposal, ReviewEvent } from '@/types/meeting';
import { ApiError } from '@/api/http';

/** A representative timeout failure from the Knowledge Brain. */
export const kbTimeout = new ApiError({
  kind: 'timeout',
  message: 'Knowledge Brain timed out after 120000ms',
});

export const kbAnswerSufficient: AskResponse = {
  answer: 'Open the member record and use the "Reset password" action, which emails a reset link.',
  citations: [
    {
      article_id: 'art-1',
      title: 'Resetting a member password',
      canonical_url: 'https://support.brilliantdirectories.com/article/reset-password',
      heading: 'Reset steps',
      chunk_id: 'chunk-1',
      chunk_index: 0,
      score: 0.91,
    },
  ],
  evidence_status: 'sufficient',
  confidence: { level: 'high', score: 0.88, basis: 'strong single-source match' },
  needs_escalation: false,
  escalation_reason: null,
  retrieved_chunks: null,
  model: 'fake',
  request_id: 'req-1',
  escalation_id: null,
};

export const kbAnswerAbstain: AskResponse = {
  answer: 'I could not find supporting evidence to answer that confidently.',
  citations: [],
  evidence_status: 'insufficient',
  confidence: { level: 'none', score: 0, basis: 'no chunk above threshold' },
  needs_escalation: true,
  escalation_reason: 'No support article covers this request.',
  retrieved_chunks: null,
  model: 'fake',
  request_id: 'req-2',
  escalation_id: 'esc-9',
};

export const inboxItemPending: InboxItem = {
  id: 'item-1',
  email: {
    id: 'email-1',
    from: 'jane@example.com',
    to: ['support@supportflow.example'],
    subject: 'How do I reset a password?',
    body: 'A member cannot log in. How do I reset their password?',
    receivedAt: '2026-01-02T10:00:00.000Z',
    threadId: null,
  },
  expected: null,
  classification: {
    category: 'product_howto',
    urgency: 'medium',
    ambiguity: 'clear',
    confidence: 0.8,
    riskFlags: [],
    needsEscalation: false,
    reasoning: 'How-to question about password reset.',
    classifier: 'rules',
    fallback: false,
  },
  originalDraft: {
    id: 'draft-1',
    emailId: 'item-1',
    body: 'Hi, you can reset a password from the member profile page.',
    grounded: true,
    citations: [
      {
        chunk_id: 'chunk-1',
        title: 'Resetting a member password',
        canonical_url: 'https://support.brilliantdirectories.com/article/reset-password',
        score: 0.91,
      },
    ],
    confirmedFacts: ['Password reset is available from the member profile page.'],
    assumptions: [],
    escalationReason: null,
    kbRequestId: 'req-1',
    kbEvidenceStatus: 'sufficient',
    kbNeedsEscalation: false,
    createdAt: '2026-01-01T10:00:00.000Z',
  },
  draft: {
    id: 'draft-1',
    emailId: 'item-1',
    body: 'Hi, you can reset a password from the member profile page.',
    grounded: true,
    citations: [
      {
        chunk_id: 'chunk-1',
        title: 'Resetting a member password',
        canonical_url: 'https://support.brilliantdirectories.com/article/reset-password',
        score: 0.91,
      },
    ],
    confirmedFacts: ['Password reset is available from the member profile page.'],
    assumptions: [],
    escalationReason: null,
    kbRequestId: 'req-1',
    kbEvidenceStatus: 'sufficient',
    kbNeedsEscalation: false,
    createdAt: '2026-01-01T10:00:00.000Z',
  },
  state: 'pending_review',
  automationExcluded: false,
  automationExclusionReasons: [],
  reviewHistory: [],
  metadata: {},
  createdAt: '2026-01-01T10:00:00.000Z',
  updatedAt: '2026-01-01T10:00:00.000Z',
};

export const kbUnavailableItem: InboxItem = {
  ...inboxItemSufficientFallback(),
};

function inboxItemSufficientFallback(): InboxItem {
  return {
    ...inboxItemPending,
    id: 'item-2',
    email: {
      ...inboxItemPending.email,
      id: 'email-2',
      subject: 'Strange question with no source',
      body: 'Can you do something we do not document?',
    },
    draft: {
      ...inboxItemPending.draft!,
      id: 'draft-2',
      emailId: 'item-2',
      body: 'Thanks for reaching out — we need to look into this and will follow up.',
      grounded: false,
      citations: [],
      confirmedFacts: [],
      escalationReason: 'Knowledge Brain unavailable (unavailable)',
      kbEvidenceStatus: 'unavailable',
      kbNeedsEscalation: true,
    },
    automationExcluded: true,
    automationExclusionReasons: ['knowledge base unavailable'],
  };
}

export const inboxListResponse = { count: 1, items: [inboxItemPending] };

export const statsResponse: StatsResponse = {
  total: 1,
  byCategory: { product_howto: 1 },
  byState: { pending_review: 1 },
  automation: {
    consecutiveUneditedApprovals: 3,
    automationEligible: false,
    automationThresholdReachedAt: null,
    threshold: 20,
  },
};

export const inboxReadyResponse: InboxReadyResponse = {
  status: 'ready',
  store: 'in-memory',
  knowledgeBrain: { reachable: true },
  automation: { consecutiveUneditedApprovals: 3, automationEligible: false, automationThresholdReachedAt: null },
};

export function reviewResult(): ReviewResultResponse {
  return {
    item: { ...inboxItemPending, state: 'approved' },
    feedback: {
      id: 'fb-1',
      itemId: 'item-1',
      draftId: 'draft-1',
      outcome: 'approved_without_edit',
      reason: null,
      edited: false,
      reviewerId: 'reviewer-1',
      at: '2026-01-01T11:00:00.000Z',
      category: 'product_howto',
    },
    automation: { consecutiveUneditedApprovals: 4, automationEligible: false, automationThresholdReachedAt: null },
    automationExcluded: false,
    automationExclusionReasons: [],
  };
}

// --- Meeting-to-Scope fixtures -------------------------------------------------

export const requirement: Requirement = {
  requirement_id: 'req-001',
  project_id: 'proj-1',
  transcript_id: 'mtg-001',
  description: 'Support up to 50,000 members without degraded performance.',
  requirement_type: 'non_functional',
  statement_kind: 'explicit',
  priority: 'high',
  rationale: null,
  acceptance_criteria: ['Directory loads within 2s at 50k members'],
  dependencies: [],
  risks: [],
  source_refs: [
    {
      transcript_id: 'mtg-001',
      segment_id: 'seg-1',
      speaker: 'Dana',
      timestamp: '00:00:30',
      quote: 'We need to support up to 50,000 members without the site slowing down.',
    },
  ],
  confidence: { level: 'high', score: 0.9, basis: 'explicit statement' },
  status: 'pending_review',
  scope: 'in_scope',
  extraction_status: 'extracted',
  conflicts_with: [],
  supersedes: null,
  notes: null,
  revision: 1,
  created_at: null,
  updated_at: null,
};

export const ingestResponse: IngestResponse = {
  transcript: {
    transcript_id: 'mtg-001',
    project_id: 'proj-1',
    title: 'Kickoff',
    meeting_date: '2026-01-12',
    sequence: 1,
    parent_transcript_id: null,
    participants: [],
    segments: [{ segment_id: 'seg-1', speaker: 'Dana', timestamp: '00:00:30', text: 'We need 50k members.' }],
    content_hash: 'abc',
  },
  requirements: [requirement],
  warnings: [],
  idempotent: false,
  change_summary: null,
  baseline_update: null,
};

export const feasibilityMap: Record<string, FeasibilityAssessment> = {
  'req-001': {
    requirement_id: 'req-001',
    project_id: 'proj-1',
    status: 'supported_by_knowledge',
    question: 'Does the platform support 50k members?',
    evidence_status: 'sufficient',
    answer: 'The platform documents scaling to large member bases.',
    citations: [
      {
        article_id: 'art-2',
        title: 'Performance and scaling',
        canonical_url: 'https://support.brilliantdirectories.com/article/scaling',
        chunk_id: 'chunk-9',
      },
    ],
    kb_request_id: 'req-kb-1',
    kb_model: 'fake',
    basis: 'knowledge match',
    error: null,
    assessed_at: '2026-01-12T00:00:00.000Z',
  },
};

export const changeSummary: ChangeSummary = {
  project_id: 'proj-1',
  from_baseline_version: 1,
  to_transcript_id: 'mtg-002',
  generated_at: '2026-01-20T00:00:00.000Z',
  counts: { added: 1, modified: 1 },
  scope_creep_count: 1,
  changes: [
    {
      change_id: 'chg-1',
      project_id: 'proj-1',
      from_baseline_version: 1,
      to_transcript_id: 'mtg-002',
      change_type: 'modified',
      requirement_id: 'req-001',
      baseline_requirement_id: 'req-001',
      summary: 'Member target increased from 50k to 75k.',
      rationale: 'Customer revised target.',
      field: 'description',
      old_value: 'Support up to 50,000 members',
      new_value: 'Support up to 75,000 members',
      new_source_refs: [],
      baseline_source_refs: [],
      confidence: { level: 'high', score: 0.9, basis: 'explicit' },
      scope_creep: true,
      estimate_impact: '+40 hours',
      status: 'proposed',
      decided_by: null,
      decided_at: null,
      decision_notes: null,
    },
    {
      change_id: 'chg-2',
      project_id: 'proj-1',
      from_baseline_version: 1,
      to_transcript_id: 'mtg-002',
      change_type: 'added',
      requirement_id: 'req-002',
      baseline_requirement_id: null,
      summary: 'Add SMS notifications.',
      rationale: 'New request.',
      field: null,
      old_value: null,
      new_value: 'Add SMS notifications',
      new_source_refs: [],
      baseline_source_refs: [],
      confidence: { level: 'medium', score: 0.6, basis: 'inferred' },
      scope_creep: false,
      estimate_impact: null,
      status: 'proposed',
      decided_by: null,
      decided_at: null,
      decision_notes: null,
    },
  ],
};

export const draftProposal: Proposal = {
  proposal_id: 'prop-1',
  project_id: 'proj-1',
  version: 1,
  status: 'draft',
  title: 'Brightpath Directory SOW',
  overview: 'A draft statement of work.',
  business_objectives: ['Scale the directory'],
  in_scope: [{ description: 'Performance improvements', requirement_ids: ['req-001'], rationale: null }],
  out_of_scope: [],
  deliverables: [{ name: 'Scalable directory', description: null, requirement_ids: ['req-001'] }],
  assumptions: ['Hosting remains unchanged'],
  dependencies: [],
  risks: [{ description: 'Deadline pressure', severity: 'high', mitigation: null, requirement_ids: [] }],
  open_questions: [{ question: 'What counts as acceptable load time?', requirement_ids: [], blocking: true }],
  acceptance_criteria: ['Loads within 2s at 50k members'],
  milestones: [],
  estimates: [
    { item: 'Caching layer', unit: 'hours', low: 40, high: 80, rationale: 'Adds cache in front of pages', dependencies: [], provisional: true, conditions: [], requirement_ids: ['req-001'] },
  ],
  exclusions: [],
  estimate_conditions: ['Assumes no third-party constraints'],
  requirement_ids: ['req-001'],
  based_on_baseline_version: null,
  created_at: '2026-01-13T00:00:00.000Z',
  approved_at: null,
  approved_by: null,
};

export const reviewEvents: ReviewEvent[] = [
  {
    id: 'ev-1',
    project_id: 'proj-1',
    entity_type: 'baseline',
    entity_id: 'base-1',
    action: 'baseline_approved',
    from_status: 'proposed',
    to_status: 'approved',
    actor: 'reviewer-1',
    reason: null,
    at: '2026-01-15T00:00:00.000Z',
  },
];
