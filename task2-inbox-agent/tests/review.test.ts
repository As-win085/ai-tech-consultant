import { applyReviewAction, evaluateAutomationExclusion, InvalidTransitionError, requiresHumanReview } from '../src/review';
import { Classification, Category, Draft } from '../src/types';

function classification(overrides: Partial<Classification> = {}): Classification {
  return {
    category: 'product_howto',
    urgency: 'low',
    ambiguity: 'clear',
    confidence: 0.9,
    riskFlags: [],
    needsEscalation: false,
    classifier: 'rules',
    fallback: false,
    ...overrides,
  };
}

function draft(overrides: Partial<Draft> = {}): Draft {
  return {
    id: 'd1',
    emailId: 'e1',
    body: 'body',
    grounded: true,
    citations: [{ chunk_id: 'c1' }],
    confirmedFacts: [],
    assumptions: [],
    escalationReason: null,
    kbRequestId: 'r1',
    kbEvidenceStatus: 'sufficient',
    kbNeedsEscalation: false,
    createdAt: '2026-01-01T00:00:00.000Z',
    ...overrides,
  };
}

describe('review state machine', () => {
  it('allows all actions from pending_review', () => {
    expect(applyReviewAction('pending_review', 'approve')).toBe('approved');
    expect(applyReviewAction('pending_review', 'edit')).toBe('edited_and_approved');
    expect(applyReviewAction('pending_review', 'reject')).toBe('rejected');
    expect(applyReviewAction('pending_review', 'escalate')).toBe('escalated');
  });

  it('rejects duplicate/invalid transitions from terminal states', () => {
    expect(() => applyReviewAction('approved', 'approve')).toThrow(InvalidTransitionError);
    expect(() => applyReviewAction('rejected', 'edit')).toThrow(InvalidTransitionError);
    expect(() => applyReviewAction('escalated', 'approve')).toThrow(InvalidTransitionError);
    expect(() => applyReviewAction('edited_and_approved', 'reject')).toThrow(InvalidTransitionError);
  });
});

describe('automation exclusion', () => {
  it('does not exclude a clear, grounded, low-risk item', () => {
    const check = evaluateAutomationExclusion(classification(), draft());
    expect(check.excluded).toBe(false);
  });

  it('excludes billing/account items', () => {
    const check = evaluateAutomationExclusion(classification({ category: 'billing_account' }), draft());
    expect(check.excluded).toBe(true);
    expect(check.reasons.join(' ')).toMatch(/billing/);
  });

  it.each(['billing_account', 'refund', 'quote', 'new_project', 'complaint', 'unsupported_unclear'] as const)(
    'always excludes the %s category from autonomous sending',
    (category: Category) => {
      const check = evaluateAutomationExclusion(classification({ category }), draft());
      expect(check.excluded).toBe(true);
      expect(check.reasons.join(' ')).toContain(category);
    },
  );

  it('does not force-review a clean follow_up item', () => {
    const check = evaluateAutomationExclusion(classification({ category: 'follow_up' }), draft());
    expect(check.excluded).toBe(false);
  });

  it('requiresHumanReview matches the always-review set', () => {
    for (const category of ['billing_account', 'refund', 'quote', 'new_project', 'complaint', 'unsupported_unclear'] as const) {
      expect(requiresHumanReview(category)).toBe(true);
    }
    expect(requiresHumanReview('follow_up')).toBe(false);
    expect(requiresHumanReview('product_howto')).toBe(false);
  });

  it('excludes items with risk flags', () => {
    const check = evaluateAutomationExclusion(classification({ riskFlags: ['account_security'] }), draft());
    expect(check.excluded).toBe(true);
  });

  it('excludes ambiguous items', () => {
    const check = evaluateAutomationExclusion(classification({ ambiguity: 'ambiguous' }), draft());
    expect(check.excluded).toBe(true);
  });

  it('excludes ungrounded drafts and inadequate evidence', () => {
    const check = evaluateAutomationExclusion(classification(), draft({ grounded: false, citations: [], kbEvidenceStatus: 'insufficient' }));
    expect(check.excluded).toBe(true);
    expect(check.reasons.join(' ')).toMatch(/grounded|evidence|citations/);
  });

  it('excludes when no draft exists', () => {
    const check = evaluateAutomationExclusion(classification(), null);
    expect(check.excluded).toBe(true);
  });
});
