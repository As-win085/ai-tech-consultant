import { config } from "./config";
import { request, probeHealth } from "./http";
import type {
  Baseline,
  BaselineUpdateProposal,
  ChangeSummary,
  FeasibilityAssessment,
  IngestResponse,
  MeetingReadyResponse,
  Participant,
  ProjectSummary,
  Proposal,
  Requirement,
  ReviewEvent,
  Transcript,
  TranscriptSegment,
} from "@/types/meeting";

/** Payload accepted by `POST /transcripts`. */
export interface TranscriptCreatePayload {
  project_id: string;
  transcript_id: string;
  title?: string;
  meeting_date?: string | null;
  sequence?: number;
  parent_transcript_id?: string | null;
  participants?: Participant[];
  segments?: TranscriptSegment[];
  text?: string;
}

/** Typed client for the Task 3 Meeting-to-Scope HTTP API. */
export const meetingApi = {
  /** GET /health — process liveness. */
  health(signal?: AbortSignal): Promise<{ status: string; service: string; version: string }> {
    return request(config.meetingUrl, "/health", { signal, timeoutMs: 5000 });
  },

  /** GET /ready — reports Knowledge Brain reachability + extractor/store. */
  ready(signal?: AbortSignal): Promise<MeetingReadyResponse> {
    return request<MeetingReadyResponse>(config.meetingUrl, "/ready", { signal, timeoutMs: 8000 });
  },

  /** POST /transcripts — ingest a transcript (idempotent on content hash). */
  ingestTranscript(
    payload: TranscriptCreatePayload,
    signal?: AbortSignal,
    timeoutMs = 90_000,
  ): Promise<IngestResponse> {
    return request<IngestResponse>(config.meetingUrl, "/transcripts", {
      method: "POST",
      body: payload,
      signal,
      timeoutMs,
    });
  },

  /** GET /projects — list known projects. */
  listProjects(signal?: AbortSignal): Promise<{ projects: ProjectSummary[] }> {
    return request(config.meetingUrl, "/projects", { signal });
  },

  /** GET /projects/:id/transcripts */
  listTranscripts(projectId: string, signal?: AbortSignal): Promise<Transcript[]> {
    return request<Transcript[]>(
      config.meetingUrl,
      `/projects/${encodeURIComponent(projectId)}/transcripts`,
      { signal },
    );
  },

  /** GET /projects/:id/requirements */
  listRequirements(projectId: string, signal?: AbortSignal): Promise<Requirement[]> {
    return request<Requirement[]>(
      config.meetingUrl,
      `/projects/${encodeURIComponent(projectId)}/requirements`,
      { signal },
    );
  },

  /** POST /projects/:id/feasibility — assess requirements against Task 1. */
  assessFeasibility(
    projectId: string,
    signal?: AbortSignal,
    timeoutMs = 120_000,
  ): Promise<Record<string, FeasibilityAssessment>> {
    return request(
      config.meetingUrl,
      `/projects/${encodeURIComponent(projectId)}/feasibility`,
      { method: "POST", signal, timeoutMs },
    );
  },

  /** POST /projects/:id/proposals — generate a draft proposal/SOW. */
  createProposal(
    projectId: string,
    body?: { version?: number | null; title?: string | null },
    signal?: AbortSignal,
    timeoutMs = 90_000,
  ): Promise<Proposal> {
    return request<Proposal>(
      config.meetingUrl,
      `/projects/${encodeURIComponent(projectId)}/proposals`,
      { method: "POST", body: body ?? {}, signal, timeoutMs },
    );
  },

  /** GET /proposals/:id */
  getProposal(proposalId: string, signal?: AbortSignal): Promise<Proposal> {
    return request<Proposal>(
      config.meetingUrl,
      `/proposals/${encodeURIComponent(proposalId)}`,
      { signal },
    );
  },

  /** POST /projects/:id/baselines — freeze a baseline. */
  createBaseline(
    projectId: string,
    body: { approved_by?: string | null; note?: string | null; proposal_id?: string | null },
    signal?: AbortSignal,
  ): Promise<Baseline> {
    return request<Baseline>(
      config.meetingUrl,
      `/projects/${encodeURIComponent(projectId)}/baselines`,
      { method: "POST", body, signal },
    );
  },

  /** GET /projects/:id/baselines */
  listBaselines(projectId: string, signal?: AbortSignal): Promise<Baseline[]> {
    return request<Baseline[]>(
      config.meetingUrl,
      `/projects/${encodeURIComponent(projectId)}/baselines`,
      { signal },
    );
  },

  /** GET /projects/:id/change-summaries */
  listChangeSummaries(projectId: string, signal?: AbortSignal): Promise<ChangeSummary[]> {
    return request<ChangeSummary[]>(
      config.meetingUrl,
      `/projects/${encodeURIComponent(projectId)}/change-summaries`,
      { signal },
    );
  },

  /** POST /projects/:id/baseline-updates/:tid/approve — approve a pending update. */
  approveBaselineUpdate(
    projectId: string,
    transcriptId: string,
    approvedBy: string,
    signal?: AbortSignal,
  ): Promise<Baseline> {
    return request<Baseline>(
      config.meetingUrl,
      `/projects/${encodeURIComponent(projectId)}/baseline-updates/${encodeURIComponent(transcriptId)}/approve`,
      { method: "POST", body: { approved_by: approvedBy }, signal },
    );
  },

  /** GET /projects/:id/events — review/audit history. */
  listEvents(projectId: string, signal?: AbortSignal): Promise<ReviewEvent[]> {
    return request<ReviewEvent[]>(
      config.meetingUrl,
      `/projects/${encodeURIComponent(projectId)}/events`,
      { signal },
    );
  },

  /** Cheap reachability probe that never throws. */
  probe(): Promise<boolean> {
    return probeHealth(config.meetingUrl);
  },
};

export type { BaselineUpdateProposal };
