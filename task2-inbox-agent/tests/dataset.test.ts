import { readFileSync } from 'fs';
import { resolve } from 'path';
import { datasetSchema } from '../src/schemas';
import { RuleBasedClassifier } from '../src/classifier';

const datasetPath = resolve(__dirname, '..', 'datasets', 'emails-sample.json');

describe('synthetic email dataset', () => {
  const raw = JSON.parse(readFileSync(datasetPath, 'utf8'));
  const parsed = datasetSchema.parse(raw);

  it('contains at least 50 emails', () => {
    expect(parsed.emails.length).toBeGreaterThanOrEqual(50);
  });

  it('has unique ids and required fields', () => {
    const ids = new Set(parsed.emails.map((e) => e.id));
    expect(ids.size).toBe(parsed.emails.length);
    for (const email of parsed.emails) {
      expect(email.from).toContain('@');
      expect(email.subject.length).toBeGreaterThan(0);
      expect(email.body.length).toBeGreaterThan(0);
    }
  });

  it('covers every intent category and includes expected labels', () => {
    const categories = new Set(parsed.emails.map((e) => e.expected?.category));
    for (const expected of [
      'product_howto',
      'troubleshooting',
      'billing_account',
      'feature_request',
      'complaint',
      'unsupported_unclear',
    ]) {
      expect(categories).toContain(expected);
    }
    expect(parsed.emails.every((e) => e.expected)).toBe(true);
  });

  it('includes urgent, risky and ambiguous cases', () => {
    const withExpected = parsed.emails.filter((e) => e.expected);
    expect(withExpected.some((e) => e.expected?.urgency === 'urgent')).toBe(true);
    expect(withExpected.some((e) => (e.expected?.riskFlags?.length ?? 0) > 0)).toBe(true);
    expect(withExpected.some((e) => e.expected?.answerability === 'ambiguous')).toBe(true);
    expect(withExpected.some((e) => e.expected?.answerability === 'unanswerable')).toBe(true);
    expect(withExpected.filter((e) => e.expected?.escalate).length).toBeGreaterThanOrEqual(15);
  });

  it('classifier roughly agrees with human labels on category', async () => {
    const classifier = new RuleBasedClassifier();
    let correct = 0;
    const emails = parsed.emails.filter((e) => e.expected);
    for (const email of emails) {
      const result = await classifier.classify({
        id: email.id ?? 'x',
        from: email.from,
        to: email.to ?? ['support@supportflow.example'],
        subject: email.subject,
        body: email.body,
        receivedAt: email.receivedAt ?? new Date().toISOString(),
        threadId: email.threadId ?? null,
      });
      if (result.category === email.expected?.category) correct += 1;
    }
    const accuracy = correct / emails.length;
    // deterministic heuristic baseline; documented in EVALS.md
    expect(accuracy).toBeGreaterThan(0.6);
  });
});
