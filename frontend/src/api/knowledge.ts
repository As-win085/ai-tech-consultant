import { config } from "./config";
import { request, probeHealth } from "./http";
import type {
  AskRequest,
  AskResponse,
  HealthReport,
  ReadyReport,
} from "@/types/knowledge";

/** Typed client for the Task 1 Knowledge Brain HTTP API. */
export const knowledgeApi = {
  /** POST /ask — ask a grounded question. */
  ask(input: AskRequest, signal?: AbortSignal, timeoutMs = 120_000): Promise<AskResponse> {
    return request<AskResponse>(config.knowledgeUrl, "/ask", {
      method: "POST",
      body: input,
      signal,
      timeoutMs,
    });
  },

  /** GET /health — process liveness only. */
  health(signal?: AbortSignal): Promise<HealthReport> {
    return request<HealthReport>(config.knowledgeUrl, "/health", { signal, timeoutMs: 5000 });
  },

  /** GET /ready — dependency readiness (database, embeddings, chat). */
  ready(signal?: AbortSignal): Promise<ReadyReport> {
    return request<ReadyReport>(config.knowledgeUrl, "/ready", { signal, timeoutMs: 8000 });
  },

  /** Cheap reachability probe that never throws. */
  probe(): Promise<boolean> {
    return probeHealth(config.knowledgeUrl);
  },
};
