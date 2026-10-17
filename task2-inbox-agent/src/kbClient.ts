import { KbAnswer } from './types';
import { kbAnswerSchema } from './schemas';

export class KnowledgeBrainError extends Error {
  readonly kind: 'timeout' | 'unavailable' | 'malformed' | 'http' | 'unknown';
  readonly status?: number;
  constructor(kind: KnowledgeBrainError['kind'], message: string, status?: number) {
    super(message);
    this.name = 'KnowledgeBrainError';
    this.kind = kind;
    this.status = status;
  }
}

export interface KbClient {
  ask(question: string): Promise<KbAnswer>;
  ping?(): Promise<boolean>;
}

export interface KnowledgeBrainClientOptions {
  baseUrl: string;
  timeoutMs: number;
  retries: number;
  fetchImpl?: typeof fetch;
}

export class KnowledgeBrainClient implements KbClient {
  private baseUrl: string;
  private timeoutMs: number;
  private retries: number;
  private fetchImpl: typeof fetch;

  constructor(opts: KnowledgeBrainClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, '');
    this.timeoutMs = opts.timeoutMs;
    this.retries = opts.retries;
    this.fetchImpl = opts.fetchImpl ?? fetch;
  }

  async ping(): Promise<boolean> {
    const controller = new AbortController();
    const timeout = Math.min(this.timeoutMs, 5000);
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const res = await this.fetchImpl(`${this.baseUrl}/health`, {
        method: 'GET',
        signal: controller.signal,
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      clearTimeout(timer);
    }
  }

  async ask(question: string): Promise<KbAnswer> {
    let lastError: KnowledgeBrainError | null = null;
    for (let attempt = 0; attempt <= this.retries; attempt++) {
      try {
        return await this.askOnce(question);
      } catch (err) {
        const e = err instanceof KnowledgeBrainError
          ? err
          : new KnowledgeBrainError('unknown', err instanceof Error ? err.message : String(err));
        lastError = e;
        const retryable = e.kind === 'timeout' || e.kind === 'unavailable' || (e.kind === 'http' && (e.status ?? 0) >= 500);
        if (!retryable || attempt === this.retries) break;
      }
    }
    throw lastError ?? new KnowledgeBrainError('unknown', 'knowledge brain request failed');
  }

  private async askOnce(question: string): Promise<KbAnswer> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}/ask`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ question }),
        signal: controller.signal,
      });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        throw new KnowledgeBrainError('timeout', `Knowledge Brain timed out after ${this.timeoutMs}ms`);
      }
      throw new KnowledgeBrainError('unavailable', `Knowledge Brain unreachable: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      clearTimeout(timer);
    }

    if (!res.ok) {
      throw new KnowledgeBrainError('http', `Knowledge Brain returned HTTP ${res.status}`, res.status);
    }

    let data: unknown;
    try {
      data = await res.json();
    } catch {
      throw new KnowledgeBrainError('malformed', 'Knowledge Brain returned non-JSON response');
    }

    const parsed = kbAnswerSchema.safeParse(data);
    if (!parsed.success) {
      throw new KnowledgeBrainError('malformed', `Knowledge Brain response failed schema validation: ${parsed.error.message}`);
    }
    return parsed.data as KbAnswer;
  }
}
