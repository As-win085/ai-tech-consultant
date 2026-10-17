import { KnowledgeBrainClient, KnowledgeBrainError } from '../src/kbClient';

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as unknown as Response;
}

const validBody = {
  answer: 'Use Settings > Security.',
  citations: [{ chunk_id: 'c1', title: 'Security' }],
  evidence_status: 'sufficient',
  needs_escalation: false,
  escalation_reason: null,
  request_id: 'req-1',
};

describe('KnowledgeBrainClient', () => {
  it('returns a validated answer on success', async () => {
    const client = new KnowledgeBrainClient({
      baseUrl: 'http://kb.test',
      timeoutMs: 1000,
      retries: 0,
      fetchImpl: (async () => jsonResponse(validBody)) as unknown as typeof fetch,
    });
    const answer = await client.ask('How do I reset my password?');
    expect(answer.request_id).toBe('req-1');
    expect(answer.citations).toHaveLength(1);
  });

  it('throws a malformed error on bad schema', async () => {
    const client = new KnowledgeBrainClient({
      baseUrl: 'http://kb.test',
      timeoutMs: 1000,
      retries: 0,
      fetchImpl: (async () => jsonResponse({ answer: 123 })) as unknown as typeof fetch,
    });
    await expect(client.ask('q')).rejects.toMatchObject({ kind: 'malformed' });
  });

  it('throws unavailable on network error', async () => {
    const client = new KnowledgeBrainClient({
      baseUrl: 'http://kb.test',
      timeoutMs: 1000,
      retries: 0,
      fetchImpl: (async () => {
        throw new Error('ECONNREFUSED');
      }) as unknown as typeof fetch,
    });
    await expect(client.ask('q')).rejects.toMatchObject({ kind: 'unavailable' });
  });

  it('throws timeout when aborted', async () => {
    const client = new KnowledgeBrainClient({
      baseUrl: 'http://kb.test',
      timeoutMs: 5,
      retries: 0,
      fetchImpl: (async (_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => {
            const err = new Error('aborted');
            err.name = 'AbortError';
            reject(err);
          });
        });
      }) as unknown as typeof fetch,
    });
    await expect(client.ask('q')).rejects.toMatchObject({ kind: 'timeout' });
  });

  it('retries retryable failures then succeeds', async () => {
    let calls = 0;
    const client = new KnowledgeBrainClient({
      baseUrl: 'http://kb.test',
      timeoutMs: 1000,
      retries: 2,
      fetchImpl: (async () => {
        calls += 1;
        if (calls === 1) throw new Error('ECONNREFUSED');
        return jsonResponse(validBody);
      }) as unknown as typeof fetch,
    });
    const answer = await client.ask('q');
    expect(answer.request_id).toBe('req-1');
    expect(calls).toBe(2);
  });

  it('does not retry a 4xx schema-ish http error beyond the limit', async () => {
    let calls = 0;
    const client = new KnowledgeBrainClient({
      baseUrl: 'http://kb.test',
      timeoutMs: 1000,
      retries: 2,
      fetchImpl: (async () => {
        calls += 1;
        return jsonResponse({}, false, 400);
      }) as unknown as typeof fetch,
    });
    await expect(client.ask('q')).rejects.toBeInstanceOf(KnowledgeBrainError);
    expect(calls).toBe(1);
  });

  it('retries 5xx http errors up to the limit', async () => {
    let calls = 0;
    const client = new KnowledgeBrainClient({
      baseUrl: 'http://kb.test',
      timeoutMs: 1000,
      retries: 2,
      fetchImpl: (async () => {
        calls += 1;
        return jsonResponse({}, false, 503);
      }) as unknown as typeof fetch,
    });
    await expect(client.ask('q')).rejects.toMatchObject({ kind: 'http', status: 503 });
    expect(calls).toBe(3);
  });
});
