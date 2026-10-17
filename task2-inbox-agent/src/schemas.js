const z = require('zod');

const emailSchema = z.object({
  id: z.string().min(1),
  from: z.string().min(1),
  to: z.array(z.string()).min(1).optional(),
  subject: z.string().min(1),
  body: z.string().min(1),
  receivedAt: z.string().datetime().optional(),
  threadId: z.string().optional(),
  priority: z.string().optional(),
});

const classificationSchema = z.object({
  category: z.enum([
    'product_howto',
    'troubleshooting',
    'billing_account',
    'feature_request',
    'complaint',
    'unsupported_unclear',
  ]),
  confidence: z.number().min(0).max(1).optional(),
  reasoning: z.string().optional(),
  needsEscalation: z.boolean().optional(),
  priority: z.enum(['low', 'medium', 'high', 'urgent']).optional(),
});

const citationSchema = z.object({
  article_id: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
  canonical_url: z.string().nullable().optional(),
  chunk_id: z.string(),
  chunk_index: z.number().optional(),
  score: z.number().optional(),
  heading: z.string().nullable().optional(),
});

const kbResponseSchema = z.object({
  answer: z.string(),
  citations: z.array(citationSchema),
  evidence_status: z.string(),
  confidence: z.object({ level: z.string(), score: z.number().nullable().optional(), basis: z.string() }).optional(),
  needs_escalation: z.boolean(),
  escalation_reason: z.string().nullable().optional(),
  retrieved_chunks: z.array(z.any()).nullable().optional(),
  model: z.string().nullable().optional(),
  request_id: z.string(),
});

const draftSchema = z.object({
  id: z.string().min(1),
  emailId: z.string().min(1),
  body: z.string().min(1),
  grounded: z.boolean(),
  citations: z.array(citationSchema),
  kbRequestId: z.string().nullable().optional(),
  kbEvidenceStatus: z.string().nullable().optional(),
  kbNeedsEscalation: z.boolean().nullable().optional(),
  createdAt: z.string(),
  notes: z.string().optional(),
});

const reviewActionSchema = z.object({
  action: z.enum(['approve', 'edit', 'reject', 'request_revision', 'escalate']),
  editedDraft: z.string().optional(),
  rejectionReason: z.string().optional(),
  escalationReason: z.string().optional(),
  feedback: z.string().optional(),
  reviewerId: z.string().optional(),
});

const inboxItemSchema = z.object({
  id: z.string().min(1),
  email: emailSchema,
  classification: classificationSchema,
  draft: draftSchema.nullable().optional(),
  state: z.enum(['pending_review', 'approved', 'edited_and_approved', 'rejected', 'escalated']),
  consecutiveUneditedApprovals: z.number().int().nonnegative(),
  reviewHistory: z.array(z.any()),
  metadata: z.record(z.any()).optional(),
});

module.exports = {
  emailSchema,
  classificationSchema,
  kbResponseSchema,
  draftSchema,
  reviewActionSchema,
  inboxItemSchema,
};
