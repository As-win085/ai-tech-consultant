import { KbClient, KnowledgeBrainError } from '../src/kbClient';
import { KbAnswer } from '../src/types';

export class MockKbClient implements KbClient {
  public calls: string[] = [];
  constructor(
    private responses:
      | KbAnswer[]
      | ((question: string) => KbAnswer | Promise<KbAnswer>),
    public reachable = true,
  ) {}

  async ask(question: string): Promise<KbAnswer> {
    this.calls.push(question);
    if (typeof this.responses === 'function') return this.responses(question);
    if (this.responses.length === 0) throw new Error('MockKbClient: no responses configured');
    const index = Math.min(this.calls.length - 1, this.responses.length - 1);
    return this.responses[index];
  }

  async ping(): Promise<boolean> {
    return this.reachable;
  }
}

export class FailingKbClient implements KbClient {
  constructor(private error: KnowledgeBrainError = new KnowledgeBrainError('unavailable', 'kb down')) {}
  async ask(): Promise<KbAnswer> {
    throw this.error;
  }
  async ping(): Promise<boolean> {
    return false;
  }
}

export function groundedAnswer(overrides: Partial<KbAnswer> = {}): KbAnswer {
  return {
    answer: 'To reset your password, open Settings > Security and choose Reset password.',
    citations: [
      {
        chunk_id: 'chunk-abc',
        article_id: 'article-1',
        title: 'Resetting your password',
        canonical_url: 'https://supportflow.example/help/reset-password',
        score: 0.82,
      },
    ],
    evidence_status: 'sufficient',
    needs_escalation: false,
    escalation_reason: null,
    request_id: 'req-1',
    model: 'test-model',
    ...overrides,
  };
}

export function abstainAnswer(overrides: Partial<KbAnswer> = {}): KbAnswer {
  return {
    answer: 'I could not find enough information to answer this.',
    citations: [],
    evidence_status: 'insufficient',
    needs_escalation: true,
    escalation_reason: 'No supporting documentation found.',
    request_id: 'req-abstain',
    model: 'test-model',
    ...overrides,
  };
}

export function sampleEmail(overrides: Record<string, unknown> = {}) {
  return {
    id: 'email-1',
    from: 'jordan@example.com',
    to: ['support@supportflow.example'],
    subject: 'How do I reset my password?',
    body: 'Hello, I cannot log in and would like to reset my password. Can you help?',
    receivedAt: '2026-01-05T10:00:00.000Z',
    threadId: null,
    ...overrides,
  };
}
