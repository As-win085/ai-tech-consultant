/**
 * Knowledge Brain (Task 1) contracts.
 *
 * Mirrors `task1-knowledge-brain/app/schemas.py`:
 * - `POST /ask` → {@link AskResponse}
 * - `GET  /health`, `GET /ready`
 */

export type EvidenceStatus = "sufficient" | "insufficient" | "conflicting" | "unavailable";
export type ConfidenceLevel = "high" | "medium" | "low" | "none";
export type ReadinessStatus = "ready" | "degraded" | "unavailable";

export interface AskRequest {
  question: string;
  top_k?: number | null;
  min_score?: number | null;
  include_chunks?: boolean;
}

export interface Citation {
  article_id: string;
  title: string;
  canonical_url: string | null;
  heading: string | null;
  chunk_id: string;
  chunk_index: number;
  score: number;
}

export interface RetrievedChunk {
  chunk_id: string;
  article_id: string;
  title: string;
  canonical_url: string | null;
  heading: string | null;
  score: number;
  content: string;
}

export interface EvidenceConfidence {
  level: ConfidenceLevel;
  score: number;
  basis: string;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  evidence_status: EvidenceStatus;
  confidence: EvidenceConfidence;
  needs_escalation: boolean;
  escalation_reason: string | null;
  retrieved_chunks: RetrievedChunk[] | null;
  model: string | null;
  request_id: string;
  escalation_id: string | null;
}

export interface DependencyStatus {
  name: string;
  status: "ok" | "error" | "not_configured" | "mismatch";
  detail: string;
}

export interface ReadyReport {
  status: ReadinessStatus;
  ready: boolean;
  dependencies: DependencyStatus[];
  index: Record<string, unknown>;
}

export interface HealthReport {
  status: string;
  service: string;
  version: string;
}
