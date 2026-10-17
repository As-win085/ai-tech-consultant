import { AppConfig } from './config';
import { buildClassifier } from './classifier';
import { KnowledgeBrainClient } from './kbClient';
import { InMemoryStore, Store } from './store';
import { PostgresStore } from './postgresStore';
import { InboxAgent } from './agent';

export interface AgentBundle {
  agent: InboxAgent;
  store: Store;
  storeKind: 'memory' | 'postgres';
}

export function buildStore(config: AppConfig): { store: Store; kind: 'memory' | 'postgres' } {
  if (config.databaseUrl) {
    return {
      store: new PostgresStore({ connectionString: config.databaseUrl, schema: config.databaseSchema }),
      kind: 'postgres',
    };
  }
  return { store: new InMemoryStore(), kind: 'memory' };
}

export async function createAgentBundle(config: AppConfig): Promise<AgentBundle> {
  const { store, kind } = buildStore(config);
  const classifier = buildClassifier(config.classifier, {
    provider: config.llmProvider,
    model: config.llmModel,
    baseUrl: config.llmBaseUrl,
    apiKey: config.llmApiKey,
    timeoutMs: config.llmTimeoutMs,
    retries: config.llmRetries,
  });
  const kbClient = new KnowledgeBrainClient({
    baseUrl: config.knowledgeBrainUrl,
    timeoutMs: config.knowledgeBrainTimeoutMs,
    retries: config.knowledgeBrainRetries,
  });
  const agent = new InboxAgent({
    store,
    classifier,
    kbClient,
    maxConsecutiveUneditedApprovals: config.maxConsecutiveUneditedApprovals,
  });
  await agent.init();
  return { agent, store, storeKind: kind };
}
