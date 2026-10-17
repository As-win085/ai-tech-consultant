import { buildServer } from '../src/server';
import { InboxAgent } from '../src/agent';
import { RuleBasedClassifier } from '../src/classifier';
import { InMemoryStore } from '../src/store';
import { loadConfig } from '../src/config';
import { groundedAnswer, abstainAnswer, MockKbClient, sampleEmail } from './helpers';

async function makeServer(kb = new MockKbClient([groundedAnswer()])) {
  const agent = new InboxAgent({
    store: new InMemoryStore(),
    classifier: new RuleBasedClassifier(),
    kbClient: kb,
  });
  await agent.init();
  const config = loadConfig({ logLevel: 'silent', port: 0 });
  const app = buildServer({ agent, config });
  return { app, agent };
}

async function ingestOne(agent: InboxAgent, email = sampleEmail()) {
  const [item] = await agent.ingestEmails([email as never]);
  return item;
}

describe('HTTP API', () => {
  it('GET /health returns ok', async () => {
    const { app } = await makeServer();
    const res = await app.inject({ method: 'GET', url: '/health' });
    expect(res.statusCode).toBe(200);
    expect(res.json().status).toBe('ok');
  });

  it('GET / serves the review UI', async () => {
    const { app } = await makeServer();
    const res = await app.inject({ method: 'GET', url: '/' });
    expect(res.statusCode).toBe(200);
    expect(res.headers['content-type']).toMatch(/text\/html/);
    expect(res.body).toMatch(/Inbox Agent/);
  });

  it('GET /ready reports ready when the knowledge brain is reachable', async () => {
    const { app } = await makeServer(new MockKbClient([groundedAnswer()], true));
    const res = await app.inject({ method: 'GET', url: '/ready' });
    expect(res.statusCode).toBe(200);
    expect(res.json().status).toBe('ready');
    expect(res.json().knowledgeBrain.reachable).toBe(true);
  });

  it('GET /ready reports degraded (still 200) when the knowledge brain is unreachable', async () => {
    const { app } = await makeServer(new MockKbClient([groundedAnswer()], false));
    const res = await app.inject({ method: 'GET', url: '/ready' });
    expect(res.statusCode).toBe(200);
    expect(res.json().status).toBe('degraded');
    expect(res.json().knowledgeBrain.reachable).toBe(false);
  });

  it('POST /emails validates the body', async () => {
    const { app } = await makeServer();
    const res = await app.inject({ method: 'POST', url: '/emails', payload: { emails: [] } });
    expect(res.statusCode).toBe(400);
    expect(res.json().error.code).toBe('validation_error');
  });

  it('POST /emails ingests and returns ids', async () => {
    const { app } = await makeServer();
    const res = await app.inject({ method: 'POST', url: '/emails', payload: { emails: [sampleEmail()] } });
    expect(res.statusCode).toBe(201);
    expect(res.json().ingested).toBe(1);
  });

  it('GET /emails/:id returns 404 for unknown ids', async () => {
    const { app } = await makeServer();
    const res = await app.inject({ method: 'GET', url: '/emails/does-not-exist' });
    expect(res.statusCode).toBe(404);
    expect(res.json().error.code).toBe('not_found');
  });

  it('runs the full draft + review flow', async () => {
    const { app, agent } = await makeServer();
    const item = await ingestOne(agent);

    const draftRes = await app.inject({ method: 'POST', url: `/emails/${item.id}/draft` });
    expect(draftRes.statusCode).toBe(200);
    expect(draftRes.json().draft.grounded).toBe(true);

    const reviewRes = await app.inject({
      method: 'POST',
      url: `/emails/${item.id}/review`,
      payload: { action: 'approve', reviewerId: 'rev-1' },
    });
    expect(reviewRes.statusCode).toBe(200);
    expect(reviewRes.json().item.state).toBe('approved');
    expect(reviewRes.json().automation.consecutiveUneditedApprovals).toBe(1);
  });

  it('returns 409 on an invalid review transition', async () => {
    const { app, agent } = await makeServer();
    const item = await ingestOne(agent);
    await app.inject({ method: 'POST', url: `/emails/${item.id}/draft` });
    await app.inject({ method: 'POST', url: `/emails/${item.id}/review`, payload: { action: 'approve' } });
    const dup = await app.inject({ method: 'POST', url: `/emails/${item.id}/review`, payload: { action: 'approve' } });
    expect(dup.statusCode).toBe(409);
    expect(dup.json().error.code).toBe('invalid_transition');
  });

  it('returns a degraded escalation draft (200) when the knowledge brain is unavailable', async () => {
    const kb = new MockKbClient(() => {
      const { KnowledgeBrainError } = require('../src/kbClient');
      throw new KnowledgeBrainError('unavailable', 'kb down');
    });
    const { app, agent } = await makeServer(kb);
    const item = await ingestOne(agent);
    const res = await app.inject({ method: 'POST', url: `/emails/${item.id}/draft` });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.draft.grounded).toBe(false);
    expect(body.draft.citations).toHaveLength(0);
    expect(body.metadata.kbError.kind).toBe('unavailable');
  });

  it('exposes feedback and stats', async () => {
    const { app, agent } = await makeServer();
    const item = await ingestOne(agent);
    await app.inject({ method: 'POST', url: `/emails/${item.id}/draft` });
    await app.inject({ method: 'POST', url: `/emails/${item.id}/review`, payload: { action: 'reject', rejectionReason: 'incorrect' } });

    const fb = await app.inject({ method: 'GET', url: '/feedback' });
    expect(fb.json().count).toBe(1);
    expect(fb.json().feedback[0].reason).toBe('incorrect');

    const stats = await app.inject({ method: 'GET', url: '/stats' });
    expect(stats.json().total).toBe(1);
    expect(stats.json().automation.threshold).toBeGreaterThan(0);
  });

  it('maps unsupported media type to 415 (not 500)', async () => {
    const { app, agent } = await makeServer();
    const item = await ingestOne(agent);
    const res = await app.inject({
      method: 'POST',
      url: `/emails/${item.id}/draft`,
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      payload: 'x=1',
    });
    expect(res.statusCode).toBe(415);
    expect(res.json().error.code).toBe('bad_request');
  });

  it('returns the audit trail for an item', async () => {
    const { app, agent } = await makeServer();
    const item = await ingestOne(agent);
    const res = await app.inject({ method: 'GET', url: `/emails/${item.id}/audit` });
    expect(res.statusCode).toBe(200);
    expect(res.json().audit.some((a: { event: string }) => a.event === 'ingested')).toBe(true);
  });
});
