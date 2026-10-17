import { z } from 'zod';
import { CATEGORIES, URGENCIES, RISK_FLAGS, ANSWERABILITY } from './types';

export const emailSchema = z.object({
  id: z.string().min(1).max(200).optional(),
  from: z.string().min(1).max(320),
  to: z.array(z.string().min(1).max(320)).max(50).optional(),
  subject: z.string().min(1).max(500),
  body: z.string().min(1).max(20000),
  receivedAt: z.string().min(1).optional(),
  threadId: z.string().max(200).nullable().optional(),
});

export const expectedLabelSchema = z.object({
  category: z.enum(CATEGORIES),
  urgency: z.enum(URGENCIES),
  riskFlags: z.array(z.enum(RISK_FLAGS)).default([]),
  answerability: z.enum(ANSWERABILITY),
  escalate: z.boolean(),
  notes: z.string().optional(),
});

export const datasetEmailSchema = emailSchema.extend({
  expected: expectedLabelSchema.optional(),
});

export const datasetSchema = z.object({
  product: z.string().optional(),
  emails: z.array(datasetEmailSchema),
});

export const classificationSchema = z.object({
  category: z.enum(CATEGORIES),
  urgency: z.enum(URGENCIES),
  ambiguity: z.enum(['clear', 'ambiguous']).default('clear'),
  confidence: z.number().min(0).max(1).default(0.5),
  riskFlags: z.array(z.enum(RISK_FLAGS)).default([]),
  needsEscalation: z.boolean().default(false),
  reasoning: z.string().optional(),
});

export const citationSchema = z.object({
  chunk_id: z.string(),
  article_id: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
  canonical_url: z.string().nullable().optional(),
  heading: z.string().nullable().optional(),
  score: z.number().nullable().optional(),
});

export const kbAnswerSchema = z.object({
  answer: z.string(),
  citations: z.array(citationSchema).default([]),
  evidence_status: z.string(),
  needs_escalation: z.boolean(),
  escalation_reason: z.string().nullable().optional(),
  request_id: z.string(),
  model: z.string().nullable().optional(),
});

export const reviewActionSchema = z.object({
  action: z.enum(['approve', 'edit', 'reject', 'escalate']),
  editedDraft: z.string().min(1).max(20000).optional(),
  rejectionReason: z.string().max(2000).optional(),
  escalationReason: z.string().max(2000).optional(),
  feedback: z.string().max(2000).optional(),
  reviewerId: z.string().max(200).optional(),
});

export const ingestRequestSchema = z.object({
  emails: z.array(emailSchema).min(1).max(500),
});

export type DatasetEmail = z.infer<typeof datasetEmailSchema>;
export type ReviewActionPayload = z.infer<typeof reviewActionSchema>;
