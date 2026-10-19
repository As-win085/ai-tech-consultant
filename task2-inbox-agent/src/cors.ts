export const DEFAULT_ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173'];

export interface OriginPolicy {
  allowAll: boolean;
  patterns: string[];
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function matchesPattern(origin: string, pattern: string): boolean {
  if (pattern === origin) return true;
  if (!pattern.includes('*')) return false;
  const source = pattern.split('*').map(escapeRegex).join('.*');
  return new RegExp(`^${source}$`).test(origin);
}

/**
 * Build an origin policy from configured origins.
 *
 * `*` opts into echoing back any origin (intentional, operator-controlled).
 * Otherwise the localhost defaults are always kept so the dev UI keeps working,
 * and configured entries may use a single `*` wildcard, e.g.
 * `https://*.vercel.app`, so preview deployments need no redeploy per branch.
 */
export function parseOrigins(configured: readonly string[]): OriginPolicy {
  const entries = configured.map((o) => o.trim()).filter(Boolean);
  if (entries.includes('*')) return { allowAll: true, patterns: [] };
  return { allowAll: false, patterns: [...new Set([...DEFAULT_ORIGINS, ...entries])] };
}

export function isOriginAllowed(origin: string, policy: OriginPolicy): boolean {
  if (policy.allowAll) return true;
  return policy.patterns.some((pattern) => matchesPattern(origin, pattern));
}
