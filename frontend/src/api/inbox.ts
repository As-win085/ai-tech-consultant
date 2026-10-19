import { config } from "./config";
import { request, probeHealth } from "./http";
import type {
  AgentState,
  AuditResponse,
  EmailListResponse,
  FeedbackRecord,
  InboxItem,
  InboxReadyResponse,
  IngestEmailsPayload,
  ReviewActionPayload,
  ReviewResultResponse,
  StatsResponse,
} from "@/types/inbox";

/** Typed client for the Task 2 Inbox Agent HTTP API. */
export const inboxApi = {
  /** GET /health — process liveness. */
  health(signal?: AbortSignal): Promise<{ status: string; version: string; service: string }> {
    return request(config.inboxUrl, "/health", { signal, timeoutMs: 5000 });
  },

  /** GET /ready — reports Knowledge Brain reachability + automation state. */
  ready(signal?: AbortSignal): Promise<InboxReadyResponse> {
    return request<InboxReadyResponse>(config.inboxUrl, "/ready", { signal, timeoutMs: 8000 });
  },

  /** GET /emails — list inbox items with optional state/category filters. */
  listEmails(
    filter?: { state?: string; category?: string },
    signal?: AbortSignal,
  ): Promise<EmailListResponse> {
    return request<EmailListResponse>(config.inboxUrl, "/emails", {
      signal,
      query: { state: filter?.state, category: filter?.category },
    });
  },

  /** GET /emails/:id — fetch a single item. */
  getEmail(id: string, signal?: AbortSignal): Promise<InboxItem> {
    return request<InboxItem>(config.inboxUrl, `/emails/${encodeURIComponent(id)}`, { signal });
  },

  /** POST /emails — ingest one or more raw emails (each gets classified). */
  ingestEmails(
    payload: IngestEmailsPayload,
    signal?: AbortSignal,
  ): Promise<{ ingested: number; items: string[] }> {
    return request(config.inboxUrl, "/emails", { method: "POST", body: payload, signal });
  },

  /** POST /emails/:id/draft — classify + ground + draft (idempotent per item). */
  generateDraft(id: string, signal?: AbortSignal, timeoutMs = 60_000): Promise<InboxItem> {
    return request<InboxItem>(config.inboxUrl, `/emails/${encodeURIComponent(id)}/draft`, {
      method: "POST",
      signal,
      timeoutMs,
    });
  },

  /** POST /emails/:id/review — approve / edit / reject / escalate. */
  review(
    id: string,
    payload: ReviewActionPayload,
    signal?: AbortSignal,
  ): Promise<ReviewResultResponse> {
    return request<ReviewResultResponse>(config.inboxUrl, `/emails/${encodeURIComponent(id)}/review`, {
      method: "POST",
      body: payload,
      signal,
    });
  },

  /** GET /emails/:id/audit — audit trail for an item. */
  audit(id: string, signal?: AbortSignal): Promise<AuditResponse> {
    return request<AuditResponse>(config.inboxUrl, `/emails/${encodeURIComponent(id)}/audit`, {
      signal,
    });
  },

  /** GET /feedback — reviewer feedback records. */
  feedback(itemId?: string, signal?: AbortSignal): Promise<{ count: number; feedback: FeedbackRecord[] }> {
    return request(config.inboxUrl, "/feedback", { signal, query: { itemId } });
  },

  /** GET /stats — counts + automation-eligibility state. */
  stats(signal?: AbortSignal): Promise<StatsResponse> {
    return request<StatsResponse>(config.inboxUrl, "/stats", { signal });
  },

  /** Cheap reachability probe that never throws. */
  probe(): Promise<boolean> {
    return probeHealth(config.inboxUrl);
  },
};

export type { AgentState };
