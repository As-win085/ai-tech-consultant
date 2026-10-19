import { readFileSync } from 'fs';
import { resolve } from 'path';
import { v4 as uuidv4 } from 'uuid';
import { Classifier } from './classifier';
import { buildDraft } from './draft';
import { KbClient, KnowledgeBrainError } from './kbClient';
import { applyReviewAction, evaluateAutomationExclusion, requiresHumanReview } from './review';
import { datasetSchema } from './schemas';
import { InMemoryStore, Store } from './store';
import {
  AgentState,
  AuditEntry,
  Category,
  CategoryAutomationState,
  Classification,
  Email,
  ExpectedLabel,
  FeedbackRecord,
  InboxItem,
  KbAnswer,
  ReviewActionInput,
  ReviewHistoryEntry,
} from './types';

function emptyCategoryState(): CategoryAutomationState {
  return { consecutiveUneditedApprovals: 0, automationEligible: false, automationThresholdReachedAt: null };
}

function ensureCategoryState(state: AgentState, category: Category): CategoryAutomationState {
  const existing = state.categories?.[category];
  if (existing) return existing;
  const fresh = emptyCategoryState();
  state.categories = { ...(state.categories ?? {}), [category]: fresh } as AgentState['categories'];
  return fresh;
}

export interface ReviewResult {
  item: InboxItem;
  feedback: FeedbackRecord;
  automationState: AgentState;
  automationExcluded: boolean;
  automationExclusionReasons: string[];
}

export interface InboxAgentOptions {
  store?: Store;
  classifier: Classifier;
  kbClient: KbClient;
  maxConsecutiveUneditedApprovals?: number;
}

export class InboxAgent {
  private store: Store;
  private classifier: Classifier;
  private kbClient: KbClient;
  private maxConsecutive: number;

  constructor(opts: InboxAgentOptions) {
    this.store = opts.store ?? new InMemoryStore();
    this.classifier = opts.classifier;
    this.kbClient = opts.kbClient;
    this.maxConsecutive = opts.maxConsecutiveUneditedApprovals ?? 20;
  }

  async init(): Promise<void> {
    await this.store.init();
  }

  async close(): Promise<void> {
    await this.store.close();
  }

  async loadDataset(filePath: string): Promise<{ loaded: number }> {
    const raw = JSON.parse(readFileSync(resolve(filePath), 'utf8'));
    const parsed = datasetSchema.parse(raw);
    const items = await this.ingestEmails(parsed.emails as never);
    return { loaded: items.length };
  }

  async ingestEmails(input: Array<Partial<Email> & { expected?: ExpectedLabel }>): Promise<InboxItem[]> {
    const items: InboxItem[] = [];
    for (const raw of input) {
      const email: Email = {
        id: raw.id ?? uuidv4(),
        from: raw.from ?? 'unknown@example.com',
        to: raw.to ?? ['support@supportflow.example'],
        subject: raw.subject ?? '(no subject)',
        body: raw.body ?? '',
        receivedAt: raw.receivedAt ?? new Date().toISOString(),
        threadId: raw.threadId ?? null,
      };
      const classification = await this.classifier.classify(email);
      const exclusion = evaluateAutomationExclusion(classification, null);
      const now = new Date().toISOString();
      const item: InboxItem = {
        id: uuidv4(),
        email,
        expected: raw.expected ?? null,
        classification,
        originalDraft: null,
        draft: null,
        state: 'pending_review',
        automationExcluded: exclusion.excluded,
        automationExclusionReasons: exclusion.reasons,
        reviewHistory: [],
        metadata: { classifier: classification.classifier },
        createdAt: now,
        updatedAt: now,
      };
      await this.store.saveItem(item);
      await this.audit(item.id, 'ingested', { category: classification.category, fallback: classification.fallback });
      items.push(item);
    }
    return items;
  }

  async listItems(filter?: { state?: InboxItem['state']; category?: InboxItem['classification']['category'] }): Promise<InboxItem[]> {
    return this.store.listItems(filter);
  }

  async getItem(id: string): Promise<InboxItem | null> {
    return this.store.getItem(id);
  }

  async generateDraft(itemId: string): Promise<InboxItem> {
    const item = await this.store.getItem(itemId);
    if (!item) throw new Error(`item not found: ${itemId}`);

    const question = `Subject: ${item.email.subject}\n\n${item.email.body}`;
    let kb: KbAnswer;
    let kbError: { kind: string; message: string } | null = null;
    try {
      kb = await this.kbClient.ask(question);
    } catch (err) {
      if (err instanceof KnowledgeBrainError) {
        // Requirement IN-FR-03: when Task 1 is unavailable, draft a clarification/escalation
        // response rather than inventing an answer. The failure is surfaced in metadata + audit.
        kbError = { kind: err.kind, message: err.message };
        kb = {
          answer: '',
          citations: [],
          evidence_status: 'unavailable',
          needs_escalation: true,
          escalation_reason: `Knowledge Brain unavailable (${err.kind}): ${err.message}`,
          request_id: 'kb-unavailable',
          model: null,
        };
      } else {
        throw err;
      }
    }
    const draft = buildDraft(item.email, kb);
    const exclusion = evaluateAutomationExclusion(item.classification, draft);

    if (!item.originalDraft) item.originalDraft = draft;
    item.draft = draft;
    item.automationExcluded = exclusion.excluded;
    item.automationExclusionReasons = exclusion.reasons;
    item.metadata.lastKb = { request_id: kb.request_id, evidence_status: kb.evidence_status, model: kb.model ?? null };
    item.metadata.kbError = kbError;
    item.updatedAt = new Date().toISOString();

    await this.store.saveItem(item);
    await this.audit(itemId, kbError ? 'draft_generation_degraded' : 'draft_generated', {
      grounded: draft.grounded,
      evidence_status: draft.kbEvidenceStatus,
      citations: draft.citations.length,
      automationExcluded: exclusion.excluded,
      kbError: kbError?.kind ?? null,
    });
    return item;
  }

  async review(itemId: string, action: ReviewActionInput): Promise<ReviewResult> {
    const item = await this.store.getItem(itemId);
    if (!item) throw new Error(`item not found: ${itemId}`);

    const fromState = item.state;
    const classification: Classification = item.classification;

    if (!item.draft) {
      // a review decision still requires a draft to act on
      throw new Error(`cannot review item ${itemId}: no draft generated yet`);
    }

    if (action.action === 'edit' && (!action.editedDraft || action.editedDraft.trim().length === 0)) {
      throw new Error('edit action requires a non-empty editedDraft');
    }

    const toState = applyReviewAction(fromState, action.action);

    let edited = false;
    if (action.action === 'edit' && action.editedDraft) {
      edited = item.draft.body !== action.editedDraft;
      item.draft = { ...item.draft, body: action.editedDraft };
    }

    const history: ReviewHistoryEntry = {
      action: action.action,
      reviewerId: action.reviewerId ?? null,
      at: new Date().toISOString(),
      fromState,
      toState,
      edited,
      feedback: action.feedback,
      rejectionReason: action.rejectionReason,
      escalationReason: action.escalationReason,
    };
    item.reviewHistory.push(history);
    item.state = toState;
    item.updatedAt = history.at;

    const exclusion = evaluateAutomationExclusion(classification, item.draft);
    item.automationExcluded = exclusion.excluded;
    item.automationExclusionReasons = exclusion.reasons;

    const outcome = outcomeFor(action.action, edited);
    const feedback: FeedbackRecord = {
      id: uuidv4(),
      itemId: item.id,
      draftId: item.draft.id,
      outcome,
      reason: action.rejectionReason ?? action.escalationReason ?? action.feedback ?? null,
      edited,
      reviewerId: action.reviewerId ?? null,
      at: history.at,
      category: classification.category,
    };

    const automationState = await this.updateAutomationCounter(outcome, edited, exclusion.excluded, classification.category);

    await this.store.saveItem(item);
    await this.store.addFeedback(feedback);
    await this.audit(itemId, 'reviewed', {
      action: action.action,
      fromState,
      toState,
      outcome,
      edited,
      automationExcluded: exclusion.excluded,
    });

    return {
      item,
      feedback,
      automationState,
      automationExcluded: exclusion.excluded,
      automationExclusionReasons: exclusion.reasons,
    };
  }

  private async updateAutomationCounter(
    outcome: FeedbackRecord['outcome'],
    edited: boolean,
    excluded: boolean,
    category: Category,
  ): Promise<AgentState> {
    const state = await this.store.getState();
    const categoryState = ensureCategoryState(state, category);
    const alwaysReview = requiresHumanReview(category);
    const isEligibleApproval =
      outcome === 'approved_without_edit' && !edited && !excluded && !alwaysReview;

    if (isEligibleApproval) {
      categoryState.consecutiveUneditedApprovals += 1;
      if (
        categoryState.consecutiveUneditedApprovals >= this.maxConsecutive &&
        !categoryState.automationEligible
      ) {
        categoryState.automationEligible = true;
        categoryState.automationThresholdReachedAt = new Date().toISOString();
        await this.audit(null, 'automation_eligible_threshold_reached', {
          category,
          count: categoryState.consecutiveUneditedApprovals,
          threshold: this.maxConsecutive,
        });
      }
    } else {
      if (categoryState.consecutiveUneditedApprovals > 0 || categoryState.automationEligible) {
        await this.audit(null, 'automation_counter_reset', {
          category,
          previousCount: categoryState.consecutiveUneditedApprovals,
          previousEligible: categoryState.automationEligible,
          reason: `outcome=${outcome} edited=${edited} excluded=${excluded}`,
        });
      }
      categoryState.consecutiveUneditedApprovals = 0;
      categoryState.automationEligible = false;
      categoryState.automationThresholdReachedAt = null;
    }

    state.categories = { ...state.categories, [category]: categoryState };
    state.consecutiveUneditedApprovals = categoryState.consecutiveUneditedApprovals;
    state.automationEligible = categoryState.automationEligible;
    state.automationThresholdReachedAt = categoryState.automationThresholdReachedAt;

    await this.store.setState(state);
    return state;
  }

  async getAutomationState(): Promise<AgentState> {
    return this.store.getState();
  }

  async kbReachable(): Promise<boolean> {
    if (!this.kbClient.ping) return false;
    try {
      return await this.kbClient.ping();
    } catch {
      return false;
    }
  }

  async getAudit(itemId?: string): Promise<AuditEntry[]> {
    return this.store.listAudit(itemId);
  }

  async getFeedback(itemId?: string): Promise<FeedbackRecord[]> {
    return this.store.listFeedback(itemId);
  }

  async audit(itemId: string | null, event: string, details: Record<string, unknown> = {}): Promise<void> {
    await this.store.addAudit({
      id: uuidv4(),
      itemId,
      event,
      at: new Date().toISOString(),
      details,
    });
  }
}

function outcomeFor(action: ReviewActionInput['action'], edited: boolean): FeedbackRecord['outcome'] {
  switch (action) {
    case 'approve':
      return 'approved_without_edit';
    case 'edit':
      return 'edited';
    case 'reject':
      return 'rejected';
    case 'escalate':
      return 'escalated';
  }
}
