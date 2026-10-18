/** Process-wide serialized model request throttle. */
let queue: Promise<void> = Promise.resolve();
let lastStartedAt = 0;

function minDelayMs(configured?: number): number {
  if (configured !== undefined) return Math.max(0, configured);
  const configuredEnv = process.env.LLM_MIN_DELAY_MS ?? process.env.LLM_REQUEST_DELAY_MS;
  if (configuredEnv !== undefined) return Math.max(0, Number(configuredEnv) || 0);
  return process.env.NODE_ENV === 'test' ? 0 : 8000;
}

export async function withGlobalModelThrottle<T>(operation: () => Promise<T>, configuredDelayMs?: number): Promise<T> {
  let release!: () => void;
  const previous = queue;
  queue = new Promise<void>((resolve) => { release = resolve; });
  await previous;
  try {
    const waitMs = minDelayMs(configuredDelayMs) - (Date.now() - lastStartedAt);
    if (waitMs > 0) await new Promise((resolve) => setTimeout(resolve, waitMs));
    lastStartedAt = Date.now();
    return await operation();
  } finally { release(); }
}

export function retryDelayMs(attempt: number, retryAfterMs = 0): number {
  const cap = Math.max(0, Number(process.env.LLM_BACKOFF_CAP_MS ?? 60000));
  const exponential = Math.min(cap, Math.max(0, Number(process.env.LLM_BACKOFF_BASE_MS ?? 1000)) * (2 ** attempt));
  return Math.max(exponential, retryAfterMs);
}

export function parseRetryAfterMs(value: string | null): number {
  if (!value) return 0;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const dateMs = Date.parse(value);
  return Number.isFinite(dateMs) ? Math.max(0, dateMs - Date.now()) : 0;
}
