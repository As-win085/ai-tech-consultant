import { KnowledgeBrainClient } from '../src/kbClient';

jest.setTimeout(300000);

const kbUrl = process.env.TEST_KB_URL;
const describeIntegration = kbUrl ? describe : describe.skip;

describeIntegration('KnowledgeBrainClient integration (opt-in via TEST_KB_URL)', () => {
  it('reaches the real Task 1 API and returns a schema-valid answer', async () => {
    const timeoutMs = Number(process.env.TEST_KB_TIMEOUT_MS ?? '300000');
    const client = new KnowledgeBrainClient({
      baseUrl: kbUrl as string,
      timeoutMs,
      retries: 0,
    });
    const answer = await client.ask('How do I add my social media accounts to the dashboard?');
    expect(typeof answer.answer).toBe('string');
    expect(Array.isArray(answer.citations)).toBe(true);
    expect(typeof answer.request_id).toBe('string');
    // The API must always return a structured, schema-valid response even when abstaining.
    expect(['sufficient', 'insufficient', 'conflicting', 'unavailable']).toContain(answer.evidence_status);
  });
});
