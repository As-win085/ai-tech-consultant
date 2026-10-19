/**
 * Meeting-to-Scope Agent (Task 3) contracts.
 *
 * Mirrors `task3-meeting-to-scope/app/schemas.py` and `app/main.py`:
 * - `POST /transcripts`, `GET /projects`, `GET /projects/:id/requirements`
 * - `POST /projects/:id/feasibility`, `POST /projects/:id/proposals`
 * - `GET  /proposals/:id`, `POST /projects/:id/baselines`
 * - `GET  /projects/:id/baselines`, `GET /projects/:id/change-summaries`
 * - `GET  /projects/:id/events`, `POST /projects/:id/baseline-updates/:tid/approve`
 */

export type RequirementType =
  | "functional"
  | "non_functional"
  | "integration"
  | "constraint"
  | "assumption"
  | "open_question";

export type Priority = "high" | "medium" | "low" | "unspecified";
export type StatementKind = "explicit" | "inferred" | "uncertain" | "proposed_solution";
export type RequirementStatus =
  | "pending_review"
  | "approved"
  | "rejected"
  | "needs_clarification";
export type ScopeDisposition = "in_scope" | "out_of_scope" | "undecided";
export type ConfidenceLevel = "high" | "medium" | "low" | "none";

export type FeasibilityStatus =
  | "supported_by_knowledge"
  | "potentially_feasible_needs_validation"
  | "not_supported_by_available_evidence"
  | "conflicting_evidence"
  | "requires_customer_clarification"
  | "assessment_unavailable"
  | "not_assessed";

export type ProposalStatus = "draft" | "in_review" | "approved" | "rejected" | "superseded";
export type BaselineStatus = "proposed" | "approved" | "superseded";
export type ChangeType =
  | "added"
  | "removed"
  | "modified"
  | "clarified"
  | "unresolved"
  | "unchanged";
export type EstimateUnit = "hours" | "days" | "points";
export type ScopeChangeStatus = "proposed" | "accepted" | "rejected" | "needs_review";

export interface Indicator {
  level: ConfidenceLevel;
  score: number;
  basis: string;
}

export interface SourceRef {
  transcript_id: string;
  segment_id: string;
  speaker: string | null;
  timestamp: string | null;
  quote: string;
}

export interface KbCitation {
  article_id?: string | null;
  title?: string | null;
  canonical_url?: string | null;
  heading?: string | null;
  chunk_id?: string | null;
  score?: number | null;
}

export interface Participant {
  name: string;
  role?: string | null;
  organization?: string | null;
  side: "customer" | "consultant" | "other";
}

export interface TranscriptSegment {
  segment_id: string;
  speaker?: string | null;
  timestamp?: string | null;
  text: string;
}

export interface Transcript {
  transcript_id: string;
  project_id: string;
  title: string;
  meeting_date: string | null;
  sequence: number;
  parent_transcript_id: string | null;
  participants: Participant[];
  segments: TranscriptSegment[];
  content_hash: string;
}

export interface Requirement {
  requirement_id: string;
  project_id: string;
  transcript_id: string;
  description: string;
  requirement_type: RequirementType;
  statement_kind: StatementKind;
  priority: Priority;
  rationale: string | null;
  acceptance_criteria: string[];
  dependencies: string[];
  risks: string[];
  source_refs: SourceRef[];
  confidence: Indicator;
  status: RequirementStatus;
  scope: ScopeDisposition;
  extraction_status: "extracted" | "needs_review" | "failed";
  conflicts_with: string[];
  supersedes: string | null;
  notes: string | null;
  revision: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface FeasibilityAssessment {
  requirement_id: string;
  project_id: string;
  status: FeasibilityStatus;
  question: string;
  evidence_status: string | null;
  answer: string | null;
  citations: KbCitation[];
  kb_request_id: string | null;
  kb_model: string | null;
  basis: string;
  error: string | null;
  assessed_at: string | null;
}

export interface ScopeItem {
  description: string;
  requirement_ids: string[];
  rationale: string | null;
}

export interface Deliverable {
  name: string;
  description: string | null;
  requirement_ids: string[];
}

export interface Risk {
  description: string;
  severity: "high" | "medium" | "low" | "unspecified";
  mitigation: string | null;
  requirement_ids: string[];
}

export interface Estimate {
  item: string;
  unit: EstimateUnit;
  low: number;
  high: number;
  rationale: string;
  dependencies: string[];
  provisional: boolean;
  conditions: string[];
  requirement_ids: string[];
}

export interface Milestone {
  milestone_id: string;
  name: string;
  objective: string;
  deliverables: string[];
  depends_on: string[];
  estimate: Estimate | null;
  requirement_ids: string[];
}

export interface OpenQuestion {
  question: string;
  requirement_ids: string[];
  blocking: boolean;
}

export interface Proposal {
  proposal_id: string;
  project_id: string;
  version: number;
  status: ProposalStatus;
  title: string;
  overview: string;
  business_objectives: string[];
  in_scope: ScopeItem[];
  out_of_scope: ScopeItem[];
  deliverables: Deliverable[];
  assumptions: string[];
  dependencies: string[];
  risks: Risk[];
  open_questions: OpenQuestion[];
  acceptance_criteria: string[];
  milestones: Milestone[];
  estimates: Estimate[];
  exclusions: string[];
  estimate_conditions: string[];
  requirement_ids: string[];
  based_on_baseline_version: number | null;
  created_at: string | null;
  approved_at: string | null;
  approved_by: string | null;
}

export interface Baseline {
  baseline_id: string;
  project_id: string;
  version: number;
  status: BaselineStatus;
  proposal_id: string | null;
  requirement_ids: string[];
  requirement_snapshot: Requirement[];
  note: string | null;
  created_at: string | null;
  approved_at: string | null;
  approved_by: string | null;
  supersedes_version: number | null;
}

export interface ScopeChange {
  change_id: string;
  project_id: string;
  from_baseline_version: number;
  to_transcript_id: string;
  change_type: ChangeType;
  requirement_id: string;
  baseline_requirement_id: string | null;
  summary: string;
  rationale: string;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  new_source_refs: SourceRef[];
  baseline_source_refs: SourceRef[];
  confidence: Indicator;
  scope_creep: boolean;
  estimate_impact: string | null;
  status: ScopeChangeStatus;
  decided_by: string | null;
  decided_at: string | null;
  decision_notes: string | null;
}

export interface ChangeSummary {
  project_id: string;
  from_baseline_version: number;
  to_transcript_id: string;
  generated_at: string;
  counts: Record<string, number>;
  scope_creep_count: number;
  changes: ScopeChange[];
}

export interface BaselineUpdateProposal {
  project_id: string;
  from_baseline_version: number;
  to_transcript_id: string;
  proposed_requirement_ids: string[];
  proposed_version: number;
  status: BaselineStatus;
  rationale: string;
  changes: ScopeChange[];
  created_at: string | null;
}

export interface ReviewEvent {
  id: string;
  project_id: string | null;
  entity_type: "requirement" | "proposal" | "baseline" | "scope_change" | "transcript";
  entity_id: string;
  action: string;
  from_status: string | null;
  to_status: string | null;
  actor: string | null;
  reason: string | null;
  at: string;
}

export interface ProjectSummary {
  project_id: string;
  name?: string;
  requirement_count?: number;
  transcript_count?: number;
  [key: string]: unknown;
}

export interface IngestResponse {
  transcript: Transcript;
  requirements: Requirement[];
  warnings: string[];
  idempotent: boolean;
  change_summary: ChangeSummary | null;
  baseline_update: BaselineUpdateProposal | null;
}

export interface MeetingReadyResponse {
  status: "ready" | "degraded";
  ready: boolean;
  extractor: string;
  store: string;
  knowledge_brain_reachable: boolean;
}
