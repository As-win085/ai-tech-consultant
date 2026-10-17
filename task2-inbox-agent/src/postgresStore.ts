import { Pool, PoolClient } from 'pg';
import {
  AgentState,
  AuditEntry,
  FeedbackRecord,
  InboxItem,
  ReviewState,
} from './types';
import { defaultAgentState, ItemFilter, Store } from './store';

interface Migration {
  version: number;
  name: string;
  statements: string[];
}

export function buildMigrations(schema: string): Migration[] {
  const s = schema;
  return [
    {
      version: 1,
      name: 'init',
      statements: [
        `CREATE SCHEMA IF NOT EXISTS ${s}`,
        `CREATE TABLE IF NOT EXISTS ${s}.schema_migrations (
           version INTEGER PRIMARY KEY,
           name TEXT NOT NULL,
           applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
         )`,
        `CREATE TABLE IF NOT EXISTS ${s}.inbox_items (
           id TEXT PRIMARY KEY,
           email JSONB NOT NULL,
           expected JSONB,
           classification JSONB NOT NULL,
           original_draft JSONB,
           draft JSONB,
           state TEXT NOT NULL,
           automation_excluded BOOLEAN NOT NULL DEFAULT FALSE,
           automation_exclusion_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
           review_history JSONB NOT NULL DEFAULT '[]'::jsonb,
           metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
           created_at TIMESTAMPTZ NOT NULL,
           updated_at TIMESTAMPTZ NOT NULL
         )`,
        `CREATE INDEX IF NOT EXISTS idx_inbox_items_state ON ${s}.inbox_items (state)`,
        `CREATE INDEX IF NOT EXISTS idx_inbox_items_category ON ${s}.inbox_items ((classification->>'category'))`,
        `CREATE TABLE IF NOT EXISTS ${s}.audit_log (
           id TEXT PRIMARY KEY,
           item_id TEXT,
           event TEXT NOT NULL,
           at TIMESTAMPTZ NOT NULL,
           details JSONB NOT NULL DEFAULT '{}'::jsonb
         )`,
        `CREATE INDEX IF NOT EXISTS idx_audit_item ON ${s}.audit_log (item_id)`,
        `CREATE TABLE IF NOT EXISTS ${s}.feedback (
           id TEXT PRIMARY KEY,
           item_id TEXT NOT NULL,
           draft_id TEXT,
           outcome TEXT NOT NULL,
           reason TEXT,
           edited BOOLEAN NOT NULL DEFAULT FALSE,
           reviewer_id TEXT,
           at TIMESTAMPTZ NOT NULL,
           category TEXT NOT NULL
         )`,
        `CREATE INDEX IF NOT EXISTS idx_feedback_item ON ${s}.feedback (item_id)`,
        `CREATE TABLE IF NOT EXISTS ${s}.agent_state (
           id INTEGER PRIMARY KEY CHECK (id = 1),
           consecutive_unedited_approvals INTEGER NOT NULL DEFAULT 0,
           automation_eligible BOOLEAN NOT NULL DEFAULT FALSE,
           automation_threshold_reached_at TIMESTAMPTZ
         )`,
        `INSERT INTO ${s}.agent_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING`,
      ],
    },
  ];
}

export interface PostgresStoreOptions {
  connectionString: string;
  schema?: string;
}

export class PostgresStore implements Store {
  private pool: Pool;
  private schema: string;
  private qualified: string;

  constructor(opts: PostgresStoreOptions) {
    this.schema = opts.schema ?? 'inbox_agent';
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(this.schema)) {
      throw new Error(`Invalid schema name: ${this.schema}`);
    }
    this.qualified = this.schema;
    this.pool = new Pool({ connectionString: opts.connectionString, max: 5 });
  }

  async init(): Promise<void> {
    const client = await this.pool.connect();
    try {
      await client.query(`CREATE SCHEMA IF NOT EXISTS ${this.schema}`);
      await client.query(
        `CREATE TABLE IF NOT EXISTS ${this.schema}.schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())`,
      );
      const applied = await client.query<{ version: number }>(`SELECT version FROM ${this.schema}.schema_migrations`);
      const appliedVersions = new Set(applied.rows.map((r) => r.version));
      for (const migration of buildMigrations(this.schema)) {
        if (appliedVersions.has(migration.version)) continue;
        await this.runMigration(client, migration);
      }
    } finally {
      client.release();
    }
  }

  private async runMigration(client: PoolClient, migration: Migration): Promise<void> {
    await client.query('BEGIN');
    try {
      for (const statement of migration.statements) {
        await client.query(statement);
      }
      await client.query(
        `INSERT INTO ${this.schema}.schema_migrations (version, name) VALUES ($1, $2)`,
        [migration.version, migration.name],
      );
      await client.query('COMMIT');
    } catch (err) {
      await client.query('ROLLBACK');
      throw err;
    }
  }

  async close(): Promise<void> {
    await this.pool.end();
  }

  async saveItem(item: InboxItem): Promise<void> {
    await this.pool.query(
      `INSERT INTO ${this.qualified}.inbox_items
        (id, email, expected, classification, original_draft, draft, state, automation_excluded, automation_exclusion_reasons, review_history, metadata, created_at, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
       ON CONFLICT (id) DO UPDATE SET
         email = EXCLUDED.email,
         expected = EXCLUDED.expected,
         classification = EXCLUDED.classification,
         original_draft = EXCLUDED.original_draft,
         draft = EXCLUDED.draft,
         state = EXCLUDED.state,
         automation_excluded = EXCLUDED.automation_excluded,
         automation_exclusion_reasons = EXCLUDED.automation_exclusion_reasons,
         review_history = EXCLUDED.review_history,
         metadata = EXCLUDED.metadata,
         updated_at = EXCLUDED.updated_at`,
      [
        item.id,
        JSON.stringify(item.email),
        item.expected ? JSON.stringify(item.expected) : null,
        JSON.stringify(item.classification),
        item.originalDraft ? JSON.stringify(item.originalDraft) : null,
        item.draft ? JSON.stringify(item.draft) : null,
        item.state,
        item.automationExcluded,
        JSON.stringify(item.automationExclusionReasons),
        JSON.stringify(item.reviewHistory),
        JSON.stringify(item.metadata),
        item.createdAt,
        item.updatedAt,
      ],
    );
  }

  async getItem(id: string): Promise<InboxItem | null> {
    const res = await this.pool.query(`SELECT * FROM ${this.qualified}.inbox_items WHERE id = $1`, [id]);
    const row = res.rows[0];
    return row ? mapItem(row) : null;
  }

  async listItems(filter?: ItemFilter): Promise<InboxItem[]> {
    const clauses: string[] = [];
    const values: unknown[] = [];
    if (filter?.state) {
      values.push(filter.state);
      clauses.push(`state = $${values.length}`);
    }
    if (filter?.category) {
      values.push(filter.category);
      clauses.push(`classification->>'category' = $${values.length}`);
    }
    const where = clauses.length ? `WHERE ${clauses.join(' AND ')}` : '';
    const res = await this.pool.query(`SELECT * FROM ${this.qualified}.inbox_items ${where}`, values);
    return res.rows.map(mapItem);
  }

  async addAudit(entry: AuditEntry): Promise<void> {
    await this.pool.query(
      `INSERT INTO ${this.qualified}.audit_log (id, item_id, event, at, details) VALUES ($1,$2,$3,$4,$5)`,
      [entry.id, entry.itemId, entry.event, entry.at, JSON.stringify(entry.details)],
    );
  }

  async listAudit(itemId?: string): Promise<AuditEntry[]> {
    const res = itemId
      ? await this.pool.query(`SELECT * FROM ${this.qualified}.audit_log WHERE item_id = $1 ORDER BY at`, [itemId])
      : await this.pool.query(`SELECT * FROM ${this.qualified}.audit_log ORDER BY at`);
    return res.rows.map((r) => ({
      id: r.id,
      itemId: r.item_id,
      event: r.event,
      at: toIso(r.at),
      details: r.details ?? {},
    }));
  }

  async addFeedback(record: FeedbackRecord): Promise<void> {
    await this.pool.query(
      `INSERT INTO ${this.qualified}.feedback (id, item_id, draft_id, outcome, reason, edited, reviewer_id, at, category)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
      [record.id, record.itemId, record.draftId, record.outcome, record.reason, record.edited, record.reviewerId, record.at, record.category],
    );
  }

  async listFeedback(itemId?: string): Promise<FeedbackRecord[]> {
    const res = itemId
      ? await this.pool.query(`SELECT * FROM ${this.qualified}.feedback WHERE item_id = $1 ORDER BY at`, [itemId])
      : await this.pool.query(`SELECT * FROM ${this.qualified}.feedback ORDER BY at`);
    return res.rows.map((r) => ({
      id: r.id,
      itemId: r.item_id,
      draftId: r.draft_id,
      outcome: r.outcome,
      reason: r.reason,
      edited: r.edited,
      reviewerId: r.reviewer_id,
      at: toIso(r.at),
      category: r.category,
    }));
  }

  async getState(): Promise<AgentState> {
    const res = await this.pool.query(`SELECT * FROM ${this.qualified}.agent_state WHERE id = 1`);
    const row = res.rows[0];
    if (!row) return defaultAgentState();
    return {
      consecutiveUneditedApprovals: row.consecutive_unedited_approvals,
      automationEligible: row.automation_eligible,
      automationThresholdReachedAt: row.automation_threshold_reached_at ? toIso(row.automation_threshold_reached_at) : null,
    };
  }

  async setState(state: AgentState): Promise<void> {
    await this.pool.query(
      `INSERT INTO ${this.qualified}.agent_state (id, consecutive_unedited_approvals, automation_eligible, automation_threshold_reached_at)
       VALUES (1,$1,$2,$3)
       ON CONFLICT (id) DO UPDATE SET
         consecutive_unedited_approvals = EXCLUDED.consecutive_unedited_approvals,
         automation_eligible = EXCLUDED.automation_eligible,
         automation_threshold_reached_at = EXCLUDED.automation_threshold_reached_at`,
      [state.consecutiveUneditedApprovals, state.automationEligible, state.automationThresholdReachedAt],
    );
  }
}

function toIso(value: Date | string): string {
  return value instanceof Date ? value.toISOString() : new Date(value).toISOString();
}

function mapItem(row: Record<string, unknown>): InboxItem {
  return {
    id: row.id as string,
    email: row.email as InboxItem['email'],
    expected: (row.expected as InboxItem['expected']) ?? null,
    classification: row.classification as InboxItem['classification'],
    originalDraft: (row.original_draft as InboxItem['originalDraft']) ?? null,
    draft: (row.draft as InboxItem['draft']) ?? null,
    state: row.state as ReviewState,
    automationExcluded: row.automation_excluded as boolean,
    automationExclusionReasons: (row.automation_exclusion_reasons as string[]) ?? [],
    reviewHistory: (row.review_history as InboxItem['reviewHistory']) ?? [],
    metadata: (row.metadata as Record<string, unknown>) ?? {},
    createdAt: toIso(row.created_at as Date),
    updatedAt: toIso(row.updated_at as Date),
  };
}
