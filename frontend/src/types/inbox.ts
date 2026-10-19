/**
 * Inbox Agent (Task 2) contracts.
 *
 * Mirrors `task2-inbox-agent/src/types.ts` and `src/schemas.ts`:
 * - `GET  /emails`, `GET /emails/:id`
 * - `POST /emails`, `POST /emails/:id/draft`, `POST /emails/:id/review`
 * - `GET  /emails/:id/audit`, `GET /feedback`, `GET /stats`, `GET /ready`
 */

export const CATEGORIES = [
  "product_howto",
  "troubleshooting",
  "billing_account",
  "feature_request",
  "complaint",
  "unsupported_unclear",
] as const;
export type Category = (typeof CATEGORIES)[number];

export const URGENCIES = ["low", "medium", "high", "urgent"] as const;
export type Urgency = (typeof URGENCIES)[number];

export const RISK_FLAGS = [
  "billing_refund",
  "account_security",
  "legal_threat",
  "pii_exposure",
  "mass_spam",
  "prompt_injection",
  "out_of_scope",
] as const;
export type RiskFlag = (typeof RISK_FLAGS)[number];

export const REVIEW_ACTIONS = ["approve", "edit", "reject", "escalate"] as const;
export type ReviewActionType = (typeof REVIEW_ACTIONS)[number];

export const REVIEW_STATES = [
  "pending_review",
  "approved",
  "edited_and_approved",
  "rejected",
  "escalated",
] as const;
export type ReviewState = (typeof REVIEW_STATES)[number];

export type EvidenceStatus = "sufficient" | "insufficient" | "conflicting" | "unavailable";

export interface Email {
  id: string;
  from: string;
  to: string[];
  subject: string;
  body: string;
  receivedAt: string;
  threadId: string | null;
}

export interface Classification {
  category: Category;
  urgency: Urgency;
  ambiguity: "clear" | "ambiguous";
  confidence: number;
  riskFlags: RiskFlag[];
  needsEscalation: boolean;
  reasoning?: string;
  classifier: string;
  fallback: boolean;
}

export interface Citation {
  chunk_id: string;
  article_id?: string | null;
  title?: string | null;
  canonical_url?: string | null;
  heading?: string | null;
  score?: number;
}

export interface Draft {
  id: string;
  emailId: string;
  body: string;
  grounded: boolean;
  citations: Citation[];
  confirmedFacts: string[];
  assumptions: string[];
  escalationReason: string | null;
  kbRequestId: string | null;
  kbEvidenceStatus: string | null;
  kbNeedsEscalation: boolean;
  createdAt: string;
}

export type ReviewActionTypeLiteral = ReviewActionType;

export interface ReviewHistoryEntry {
  action: ReviewActionType;
  reviewerId: string | null;
  at: string;
  fromState: ReviewState;
  toState: ReviewState;
  edited: boolean;
  feedback?: string;
  rejectionReason?: string;
  escalationReason?: string;
}

export type FeedbackOutcome =
  | "approved_without_edit"
  | "edited"
  | "rejected"
  | "escalated";

export interface FeedbackRecord {
  id: string;
  itemId: string;
  draftId: string | null;
  outcome: FeedbackOutcome;
  reason: string | null;
  edited: boolean;
  reviewerId: string | null;
  at: string;
  category: Category;
}

export interface AuditEntry {
  id: string;
  itemId: string | null;
  event: string;
  at: string;
  details: Record<string, unknown>;
}

export interface InboxItem {
  id: string;
  email: Email;
  expected: unknown | null;
  classification: Classification;
  originalDraft: Draft | null;
  draft: Draft | null;
  state: ReviewState;
  automationExcluded: boolean;
  automationExclusionReasons: string[];
  reviewHistory: ReviewHistoryEntry[];
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface AgentState {
  consecutiveUneditedApprovals: number;
  automationEligible: boolean;
  automationThresholdReachedAt: string | null;
}

export interface EmailListResponse {
  count: number;
  items: InboxItem[];
}

export interface ReviewResultResponse {
  item: InboxItem;
  feedback: FeedbackRecord;
  automation: AgentState;
  automationExcluded: boolean;
  automationExclusionReasons: string[];
}

export interface AuditResponse {
  count: number;
  audit: AuditEntry[];
}

export interface StatsResponse {
  total: number;
  byCategory: Record<string, number>;
  byState: Record<string, number>;
  automation: AgentState & { threshold: number };
}

export interface InboxReadyResponse {
  status: "ready" | "degraded";
  store: string;
  knowledgeBrain: { reachable: boolean };
  automation: AgentState;
}

export interface ReviewActionPayload {
  action: ReviewActionType;
  editedDraft?: string;
  rejectionReason?: string;
  escalationReason?: string;
  feedback?: string;
  reviewerId?: string;
}

export interface IngestEmailsPayload {
  emails: Array<Pick<Email, "from" | "subject" | "body"> & { to?: string[]; receivedAt?: string }>;
}
