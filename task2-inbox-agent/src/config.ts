import * as dotenv from 'dotenv';

dotenv.config();

export interface AppConfig {
  port: number;
  host: string;
  trustProxy: boolean;
  allowedOrigins: string[];
  knowledgeBrainUrl: string;
  knowledgeBrainTimeoutMs: number;
  knowledgeBrainRetries: number;
  classifier: 'rules' | 'llm';
  llmProvider: 'openai_compatible' | 'anthropic' | 'gemini' | 'google' | 'groq' | 'openrouter' | 'ollama';
  llmModel: string;
  llmBaseUrl: string | null;
  llmApiKey: string | null;
  llmTimeoutMs: number;
  llmRetries: number;
  llmRequestDelayMs: number;
  embeddingProvider: string;
  embeddingModel: string;
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

function listEnv(name: string): string[] {
  const raw = process.env[name];
  if (!raw) return [];
  return raw.split(',').map((entry) => entry.trim()).filter(Boolean);
}

function boolEnv(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw === undefined || raw === '') return fallback;
  return ['1', 'true', 'yes', 'on'].includes(raw.trim().toLowerCase());
}

export function loadConfig(overrides: Partial<AppConfig> = {}): AppConfig {
  const classifier = (process.env.CLASSIFIER ?? 'rules').toLowerCase();
  if (classifier !== 'rules' && classifier !== 'llm') {
    throw new Error(`CLASSIFIER must be "rules" or "llm", got "${classifier}"`);
  }
  const llmProvider = (process.env.LLM_PROVIDER ?? 'gemini').toLowerCase();
  if (!['openai_compatible', 'anthropic', 'gemini', 'google', 'groq', 'openrouter', 'ollama'].includes(llmProvider)) {
    throw new Error(`Unsupported LLM_PROVIDER: ${llmProvider}`);
  }
  const providerKey = llmProvider === 'openrouter' ? process.env.OPENROUTER_API_KEY
    : llmProvider === 'groq' ? process.env.GROQ_API_KEY
      : llmProvider === 'gemini' || llmProvider === 'google' ? process.env.GEMINI_API_KEY
        : llmProvider === 'anthropic' ? process.env.ANTHROPIC_API_KEY : undefined;

  const config: AppConfig = {
    port: intEnv('PORT', 8080),
    host: process.env.HOST?.trim() || '',
    trustProxy: boolEnv('TRUST_PROXY', false),
    allowedOrigins: listEnv('ALLOWED_ORIGINS'),
    knowledgeBrainUrl: process.env.KNOWLEDGE_BRAIN_URL ?? 'http://localhost:8000',
    knowledgeBrainTimeoutMs: intEnv('KNOWLEDGE_BRAIN_TIMEOUT_MS', 30000),
    knowledgeBrainRetries: intEnv('KNOWLEDGE_BRAIN_RETRIES', 2),
    classifier: classifier as AppConfig['classifier'],
    llmProvider: llmProvider as AppConfig['llmProvider'],
    llmModel: process.env.LLM_MODEL ?? process.env.CHAT_MODEL ?? 'gemini-3.8-flash',
    llmBaseUrl: (process.env.LLM_BASE_URL || process.env.CHAT_BASE_URL || ({
      gemini: 'https://generativelanguage.googleapis.com/v1beta/openai',
      google: 'https://generativelanguage.googleapis.com/v1beta/openai',
      groq: 'https://api.groq.com/openai/v1', openrouter: 'https://openrouter.ai/api/v1',
      ollama: 'http://localhost:11434/v1',
    } as Record<string, string>)[llmProvider]) ?? null,
    llmApiKey: providerKey ?? process.env.LLM_API_KEY ?? null,
    llmTimeoutMs: intEnv('LLM_TIMEOUT_MS', 60000),
    llmRetries: intEnv('LLM_RETRIES', 1),
    llmRequestDelayMs: intEnv('LLM_MIN_DELAY_MS', intEnv('LLM_REQUEST_DELAY_MS', 8000)),
    embeddingProvider: process.env.EMBEDDING_PROVIDER ?? 'gemini',
    embeddingModel: process.env.EMBEDDING_MODEL ?? 'gemini-embedding-001',
    maxConsecutiveUneditedApprovals: intEnv('MAX_CONSECUTIVE_UNEDITED_APPROVALS', 20),
    databaseUrl: process.env.DATABASE_URL ?? null,
    databaseSchema: process.env.DATABASE_SCHEMA ?? 'inbox_agent',
    logLevel: process.env.LOG_LEVEL ?? 'info',
    datasetPath: process.env.EMAIL_DATASET_PATH ?? 'datasets/emails-sample.json',
  };

  return { ...config, ...overrides };
}
