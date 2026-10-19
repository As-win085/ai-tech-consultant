import { DEFAULT_ORIGINS, isOriginAllowed, parseOrigins } from '../src/cors';

describe('cors origin policy', () => {
  it('always allows the localhost dev origins', () => {
    const policy = parseOrigins([]);
    for (const origin of DEFAULT_ORIGINS) {
      expect(isOriginAllowed(origin, policy)).toBe(true);
    }
  });

  it('allows an exactly configured origin and rejects others', () => {
    const policy = parseOrigins(['https://app.example.com']);
    expect(isOriginAllowed('https://app.example.com', policy)).toBe(true);
    expect(isOriginAllowed('https://evil.example.com', policy)).toBe(false);
  });

  it('supports wildcard subdomain patterns', () => {
    const policy = parseOrigins(['https://*.vercel.app']);
    expect(isOriginAllowed('https://ai-tech.vercel.app', policy)).toBe(true);
    expect(isOriginAllowed('https://preview-branch.vercel.app', policy)).toBe(true);
    expect(isOriginAllowed('https://vercel.app', policy)).toBe(false);
    expect(isOriginAllowed('https://vercel.app.evil.com', policy)).toBe(false);
  });

  it('does not let a wildcard escape as a bare prefix', () => {
    const policy = parseOrigins(['https://*.example.com']);
    expect(isOriginAllowed('https://example.com', policy)).toBe(false);
    expect(isOriginAllowed('https://a.example.com.attacker.test', policy)).toBe(false);
  });

  it('ignores blank and whitespace entries', () => {
    const policy = parseOrigins(['  ', '', '  https://app.example.com  ']);
    expect(policy.patterns).toEqual([...DEFAULT_ORIGINS, 'https://app.example.com']);
    expect(isOriginAllowed('https://app.example.com', policy)).toBe(true);
  });

  it('deduplicates configured origins', () => {
    const policy = parseOrigins(['http://localhost:5173', 'http://localhost:5173']);
    expect(policy.patterns).toEqual(DEFAULT_ORIGINS);
  });

  it('opts into allow-all only on an explicit "*" entry', () => {
    const policy = parseOrigins(['*']);
    expect(policy.allowAll).toBe(true);
    expect(isOriginAllowed('https://anything.example', policy)).toBe(true);
  });

  it('treats "*" embedded in a longer entry as a pattern, not allow-all', () => {
    const policy = parseOrigins(['https://*.onrender.com']);
    expect(policy.allowAll).toBe(false);
    expect(isOriginAllowed('https://inbox-agent.onrender.com', policy)).toBe(true);
  });
});
