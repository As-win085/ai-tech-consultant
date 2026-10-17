import { Client } from 'pg';
import { PostgresStore } from '../src/postgresStore';
import { InboxAgent } from '../src/agent';
import { RuleBasedClassifier } from '../src/classifier';
import { groundedAnswer, MockKbClient, sampleEmail } from './helpers';

const connectionString = process.env.TEST_DATABASE_URL;
const schema = process.env.TEST_DATABASE_SCHEMA ?? 'inbox_agent_test';
const describeIntegration = connectionString ? describe : describe.skip;

describeIntegration('PostgresStore integration (opt-in via TEST_DATABASE_URL)', () => {
  let store: PostgresStore;
  let agent: InboxAgent;

  beforeAll(async () => {
    store = new PostgresStore({ connectionString: connectionString as string, schema });
    await store.init();
    agent = new InboxAgent({
      store,
      classifier: new RuleBasedClassifier(),
      kbClient: new MockKbClient([groundedAnswer()]),
    });
    await agent.init();
  });

  afterAll(async () => {
    if (!connectionString) return;
    const client = new Client({ connectionString });
    await client.connect();
    await client.query(`DROP SCHEMA IF EXISTS ${schema} CASCADE`);
    await client.end();
    await store.close();
  });

  it('applies migrations idempotently', async () => {
    await store.init();
    const client = new Client({ connectionString });
    await client.connect();
    const res = await client.query(`SELECT version FROM ${schema}.schema_migrations ORDER BY version`);
    await client.end();
    expect(res.rows.map((r) => r.version)).toContain(1);
  });

  it('persists items, audit, feedback and automation state across store instances', async () => {
    const [item] = await agent.ingestEmails([sampleEmail({ id: 'pg-1' }) as never]);
    await agent.generateDraft(item.id);
    const result = await agent.review(item.id, { action: 'approve' });
    expect(result.automationState.consecutiveUneditedApprovals).toBe(1);

    const fresh = new PostgresStore({ connectionString: connectionString as string, schema });
    await fresh.init();
    const loaded = await fresh.getItem(item.id);
    expect(loaded).not.toBeNull();
    expect(loaded?.state).toBe('approved');
    expect(loaded?.draft?.grounded).toBe(true);

    const audit = await fresh.listAudit(item.id);
    expect(audit.some((a) => a.event === 'reviewed')).toBe(true);

    const feedback = await fresh.listFeedback(item.id);
    expect(feedback).toHaveLength(1);

    const state = await fresh.getState();
    expect(state.consecutiveUneditedApprovals).toBe(1);
    await fresh.close();
  });
});
