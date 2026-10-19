/**
 * Centralized HTTP layer shared by all three service clients.
 *
 * Responsibilities:
 * - Normalize network failures, timeouts, HTTP errors, and malformed JSON into
 *   a single {@link ApiError} type with a machine-readable `code`.
 * - Propagate the backends' documented error body shape
 *   (`{ error: { code, message, request_id } }`).
 * - Accept an `AbortSignal` so callers can cancel in-flight requests.
 *
 * No error path may silently swallow a failure — every failure becomes a typed
 * {@link ApiError} that surfaces to the UI.
 */

export type ApiErrorKind =
  | "network"
  | "timeout"
  | "http"
  | "malformed"
  | "aborted"
  | "unknown";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly code: string;
  readonly requestId?: string;
  readonly detail?: string;

  constructor(params: {
    kind: ApiErrorKind;
    message: string;
    status?: number;
    code?: string;
    requestId?: string;
    detail?: string;
  }) {
    super(params.message);
    this.name = "ApiError";
    this.kind = params.kind;
    this.status = params.status;
    this.code = params.code ?? params.kind;
    this.requestId = params.requestId;
    this.detail = params.detail;
  }

  /** True when an automatic retry could plausibly succeed. */
  get retryable(): boolean {
    if (this.kind === "timeout" || this.kind === "network") return true;
    if (this.kind === "http") return (this.status ?? 0) >= 500;
    return false;
  }

  /** True when the request was cancelled by the caller. */
  get isAbort(): boolean {
    return this.kind === "aborted";
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
  query?: Record<string, string | number | boolean | undefined | null>;
}

const DEFAULT_TIMEOUT_MS = 30_000;

function buildUrl(baseUrl: string, path: string, query?: RequestOptions["query"]): string {
  const url = `${baseUrl.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; request_id?: string };
}

export async function request<T>(baseUrl: string, path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, timeoutMs = DEFAULT_TIMEOUT_MS, query } = options;
  const url = buildUrl(baseUrl, path, query);

  // Compose the caller's signal with a timeout so both can abort the request.
  const controller = new AbortController();
  const onExternalAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", onExternalAbort, { once: true });
  }
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: body !== undefined ? { "content-type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    if (isAbortError(err)) {
      // Distinguish caller cancellation from our own timeout.
      if (signal?.aborted) {
        throw new ApiError({ kind: "aborted", message: "Request cancelled" });
      }
      throw new ApiError({
        kind: "timeout",
        message: `Request to ${path} timed out after ${timeoutMs}ms`,
        detail: String(err),
      });
    }
    throw new ApiError({
      kind: "network",
      message: `Could not reach ${baseUrl}`,
      detail: err instanceof Error ? err.message : String(err),
    });
  } finally {
    clearTimeout(timer);
    if (signal) signal.removeEventListener("abort", onExternalAbort);
  }

  if (!response.ok) {
    const envelope = await safeJson<ErrorEnvelope>(response);
    throw new ApiError({
      kind: "http",
      status: response.status,
      message: envelope?.error?.message ?? `${method} ${path} failed with HTTP ${response.status}`,
      code: envelope?.error?.code ?? `http_${response.status}`,
      requestId: envelope?.error?.request_id,
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const parsed = await safeJson<T>(response);
  if (parsed === undefined) {
    throw new ApiError({
      kind: "malformed",
      status: response.status,
      message: `Expected a JSON response from ${path} but received something unreadable`,
    });
  }
  return parsed;
}

async function safeJson<T>(response: Response): Promise<T | undefined> {
  try {
    return (await response.json()) as T;
  } catch {
    return undefined;
  }
}

function isAbortError(err: unknown): boolean {
  return (
    typeof err === "object" &&
    err !== null &&
    (err as { name?: string }).name === "AbortError"
  );
}

/** Health probe that never throws — used for connectivity badges. */
export async function probeHealth(baseUrl: string, signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl.replace(/\/$/, "")}/health`, {
      method: "GET",
      signal: signal ?? AbortSignal.timeout(4000),
    });
    return res.ok;
  } catch {
    return false;
  }
}
