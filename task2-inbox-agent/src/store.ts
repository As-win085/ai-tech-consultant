import { AgentState, AuditEntry, Category, FeedbackRecord, InboxItem, ReviewState } from './types';

export interface ItemFilter {
  state?: ReviewState;
  category?: Category;
}

export interface Store {
  init(): Promise<void>;
  close(): Promise<void>;
  saveItem(item: InboxItem): Promise<void>;
  getItem(id: string): Promise<InboxItem | null>;
  listItems(filter?: ItemFilter): Promise<InboxItem[]>;
  addAudit(entry: AuditEntry): Promise<void>;
  listAudit(itemId?: string): Promise<AuditEntry[]>;
  addFeedback(record: FeedbackRecord): Promise<void>;
  listFeedback(itemId?: string): Promise<FeedbackRecord[]>;
  getState(): Promise<AgentState>;
  setState(state: AgentState): Promise<void>;
}

export function defaultAgentState(): AgentState {
  return { consecutiveUneditedApprovals: 0, automationEligible: false, automationThresholdReachedAt: null };
}

export class InMemoryStore implements Store {
  private items = new Map<string, InboxItem>();
  private audit: AuditEntry[] = [];
  private feedback: FeedbackRecord[] = [];
  private state: AgentState = defaultAgentState();

  async init(): Promise<void> {}
  async close(): Promise<void> {}

  async saveItem(item: InboxItem): Promise<void> {
    this.items.set(item.id, clone(item));
  }

  async getItem(id: string): Promise<InboxItem | null> {
    const item = this.items.get(id);
    return item ? clone(item) : null;
  }

  async listItems(filter?: ItemFilter): Promise<InboxItem[]> {
    let items = [...this.items.values()];
    if (filter?.state) items = items.filter((i) => i.state === filter.state);
    if (filter?.category) items = items.filter((i) => i.classification.category === filter.category);
    return items.map(clone);
  }

  async addAudit(entry: AuditEntry): Promise<void> {
    this.audit.push(clone(entry));
  }

  async listAudit(itemId?: string): Promise<AuditEntry[]> {
    const entries = itemId ? this.audit.filter((a) => a.itemId === itemId) : this.audit;
    return entries.map(clone);
  }

  async addFeedback(record: FeedbackRecord): Promise<void> {
    this.feedback.push(clone(record));
  }

  async listFeedback(itemId?: string): Promise<FeedbackRecord[]> {
    const records = itemId ? this.feedback.filter((f) => f.itemId === itemId) : this.feedback;
    return records.map(clone);
  }

  async getState(): Promise<AgentState> {
    return { ...this.state };
  }

  async setState(state: AgentState): Promise<void> {
    this.state = { ...state };
  }
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
