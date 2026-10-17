import * as dotenv from 'dotenv';

dotenv.config();

export interface AppConfig {
  port: number;
  knowledgeBrainUrl: string;
  knowledgeBrainTimeoutMs: number;
  knowledgeBrainRetries: number;
  classifier: 'rules' | 'llm';
  llmProvider: 'openai_compatible' | 'anthropic';
  llmModel: string;
  llmBaseUrl: string | null;
  llmApiKey: string | null;
  llmTimeoutMs: number;
  llmRetries: number;
  maxConsecutiveUneditedApprovals: number;
  databaseUrl: string | null;
  databaseSchema: string;
  logLevel: string;
  datasetPath: string;
}

function intEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  if (raw === undefined || raw === '') return fallback;
  const n = Number.parseInt(raw, 10);
  if (Number.isNaN(n)) {
    throw new Error(`Invalid integer for ${name}: ${raw}`);
  }
  return n;
}

export function loadConfig(overrides: Partial<AppConfig> = {}): AppConfig {
  const classifier = (process.env.CLASSIFIER ?? 'rules').toLowerCase();
  if (classifier !== 'rules' && classifier !== 'llm') {
    throw new Error(`CLASSIFIER must be "rules" or "llm", got "${classifier}"`);
  }
  const llmProvider = (process.env.LLM_PROVIDER ?? 'openai_compatible').toLowerCase();
  if (llmProvider !== 'openai_compatible' && llmProvider !== 'anthropic') {
    throw new Error(`LLM_PROVIDER must be "openai_compatible" or "anthropic", got "${llmProvider}"`);
  }

  const config: AppConfig = {
    port: intEnv('PORT', 8080),
    knowledgeBrainUrl: process.env.KNOWLEDGE_BRAIN_URL ?? 'http://localhost:8000',
    knowledgeBrainTimeoutMs: intEnv('KNOWLEDGE_BRAIN_TIMEOUT_MS', 30000),
    knowledgeBrainRetries: intEnv('KNOWLEDGE_BRAIN_RETRIES', 2),
    classifier: classifier as AppConfig['classifier'],
    llmProvider: llmProvider as AppConfig['llmProvider'],
    llmModel: process.env.LLM_MODEL ?? process.env.CHAT_MODEL ?? 'llama3.2:1b',
    llmBaseUrl: process.env.LLM_BASE_URL ?? process.env.CHAT_BASE_URL ?? null,
    llmApiKey: process.env.LLM_API_KEY ?? process.env.ANTHROPIC_API_KEY ?? null,
    llmTimeoutMs: intEnv('LLM_TIMEOUT_MS', 60000),
    llmRetries: intEnv('LLM_RETRIES', 1),
    maxConsecutiveUneditedApprovals: intEnv('MAX_CONSECUTIVE_UNEDITED_APPROVALS', 20),
    databaseUrl: process.env.DATABASE_URL ?? null,
    databaseSchema: process.env.DATABASE_SCHEMA ?? 'inbox_agent',
    logLevel: process.env.LOG_LEVEL ?? 'info',
    datasetPath: process.env.EMAIL_DATASET_PATH ?? 'datasets/emails-sample.json',
  };

  return { ...config, ...overrides };
}
