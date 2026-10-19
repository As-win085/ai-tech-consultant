import { Category, Classification, Draft, ReviewActionType, ReviewState } from './types';

export const ALWAYS_REVIEW_CATEGORIES: ReadonlyArray<Category> = [
  'billing_account',
  'refund',
  'quote',
  'new_project',
  'complaint',
  'unsupported_unclear',
];

export function requiresHumanReview(category: Category): boolean {
  return ALWAYS_REVIEW_CATEGORIES.includes(category);
}

export class InvalidTransitionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'InvalidTransitionError';
  }
}

const ALLOWED_TRANSITIONS: Record<ReviewState, ReviewActionType[]> = {
  pending_review: ['approve', 'edit', 'reject', 'escalate'],
  approved: [],
  edited_and_approved: [],
  rejected: [],
  escalated: [],
};

export function applyReviewAction(current: ReviewState, action: ReviewActionType): ReviewState {
  if (!ALLOWED_TRANSITIONS[current].includes(action)) {
    throw new InvalidTransitionError(`Action "${action}" is not valid from state "${current}"`);
  }
  switch (action) {
    case 'approve':
      return 'approved';
    case 'edit':
      return 'edited_and_approved';
    case 'reject':
      return 'rejected';
    case 'escalate':
      return 'escalated';
  }
}

export interface AutomationCheck {
  excluded: boolean;
  reasons: string[];
}

const DEFAULT_MIN_CONFIDENCE = 0.6;

export function evaluateAutomationExclusion(
  classification: Classification,
  draft: Draft | null,
  minConfidence = DEFAULT_MIN_CONFIDENCE,
): AutomationCheck {
  const reasons: string[] = [];
  if (classification.riskFlags.length > 0) {
    reasons.push(`risk flags present: ${classification.riskFlags.join(', ')}`);
  }
  if (requiresHumanReview(classification.category)) {
    reasons.push(`${classification.category} category always requires human review`);
  }
  if (classification.ambiguity === 'ambiguous') reasons.push('ambiguous request');
  if (classification.confidence < minConfidence) reasons.push(`low confidence (${classification.confidence})`);
  if (classification.needsEscalation) reasons.push('classification flagged for escalation');
  if (!draft) reasons.push('no draft available');
  else {
    if (!draft.grounded) reasons.push('draft not grounded in evidence');
    if (!draft.citations || draft.citations.length === 0) reasons.push('draft has no citations');
    if (draft.kbEvidenceStatus !== 'sufficient') reasons.push(`inadequate evidence (${draft.kbEvidenceStatus})`);
  }
  return { excluded: reasons.length > 0, reasons };
}
