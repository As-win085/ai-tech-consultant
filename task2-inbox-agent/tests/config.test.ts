import { loadConfig } from '../src/config';

describe('host, proxy and CORS configuration', () => {
  it('defaults to auto host, no trusted proxy and no extra origins', () => {
    const previous = { host: process.env.HOST, trust: process.env.TRUST_PROXY, origins: process.env.ALLOWED_ORIGINS };
    delete process.env.HOST;
    delete process.env.TRUST_PROXY;
    delete process.env.ALLOWED_ORIGINS;
    try {
      const config = loadConfig();
      expect(config.host).toBe('');
      expect(config.trustProxy).toBe(false);
      expect(config.allowedOrigins).toEqual([]);
    } finally {
      if (previous.host === undefined) delete process.env.HOST; else process.env.HOST = previous.host;
      if (previous.trust === undefined) delete process.env.TRUST_PROXY; else process.env.TRUST_PROXY = previous.trust;
      if (previous.origins === undefined) delete process.env.ALLOWED_ORIGINS; else process.env.ALLOWED_ORIGINS = previous.origins;
    }
  });

  it('reads HOST, TRUST_PROXY and comma-separated ALLOWED_ORIGINS', () => {
    const previous = { host: process.env.HOST, trust: process.env.TRUST_PROXY, origins: process.env.ALLOWED_ORIGINS };
    process.env.HOST = '0.0.0.0';
    process.env.TRUST_PROXY = 'true';
    process.env.ALLOWED_ORIGINS = 'https://app.example.com, https://*.vercel.app';
    try {
      const config = loadConfig();
      expect(config.host).toBe('0.0.0.0');
      expect(config.trustProxy).toBe(true);
      expect(config.allowedOrigins).toEqual(['https://app.example.com', 'https://*.vercel.app']);
    } finally {
      if (previous.host === undefined) delete process.env.HOST; else process.env.HOST = previous.host;
      if (previous.trust === undefined) delete process.env.TRUST_PROXY; else process.env.TRUST_PROXY = previous.trust;
      if (previous.origins === undefined) delete process.env.ALLOWED_ORIGINS; else process.env.ALLOWED_ORIGINS = previous.origins;
    }
  });
});

describe('provider-specific generation credentials', () => {
  it('uses the OpenRouter key before the generic key when OpenRouter is selected', () => {
    const previous = {
      provider: process.env.LLM_PROVIDER,
      specific: process.env.OPENROUTER_API_KEY,
      generic: process.env.LLM_API_KEY,
      base: process.env.LLM_BASE_URL,
      chatBase: process.env.CHAT_BASE_URL,
    };
    process.env.LLM_PROVIDER = 'openrouter';
    process.env.OPENROUTER_API_KEY = 'openrouter-test-only';
    process.env.LLM_API_KEY = 'generic-test-only';
    delete process.env.LLM_BASE_URL;
    delete process.env.CHAT_BASE_URL;
    try {
      expect(loadConfig().llmApiKey).toBe('openrouter-test-only');
      expect(loadConfig().llmBaseUrl).toBe('https://openrouter.ai/api/v1');
    } finally {
      if (previous.provider === undefined) delete process.env.LLM_PROVIDER; else process.env.LLM_PROVIDER = previous.provider;
      if (previous.specific === undefined) delete process.env.OPENROUTER_API_KEY; else process.env.OPENROUTER_API_KEY = previous.specific;
      if (previous.generic === undefined) delete process.env.LLM_API_KEY; else process.env.LLM_API_KEY = previous.generic;
      if (previous.base === undefined) delete process.env.LLM_BASE_URL; else process.env.LLM_BASE_URL = previous.base;
      if (previous.chatBase === undefined) delete process.env.CHAT_BASE_URL; else process.env.CHAT_BASE_URL = previous.chatBase;
    }
  });

  it('uses the Groq key when Groq is selected', () => {
    const previous = { provider: process.env.LLM_PROVIDER, specific: process.env.GROQ_API_KEY, base: process.env.LLM_BASE_URL, chatBase: process.env.CHAT_BASE_URL };
    process.env.LLM_PROVIDER = 'groq';
    process.env.GROQ_API_KEY = 'groq-test-only';
    delete process.env.LLM_BASE_URL;
    delete process.env.CHAT_BASE_URL;
    try {
      expect(loadConfig().llmApiKey).toBe('groq-test-only');
      expect(loadConfig().llmBaseUrl).toBe('https://api.groq.com/openai/v1');
    } finally {
      if (previous.provider === undefined) delete process.env.LLM_PROVIDER; else process.env.LLM_PROVIDER = previous.provider;
      if (previous.specific === undefined) delete process.env.GROQ_API_KEY; else process.env.GROQ_API_KEY = previous.specific;
      if (previous.base === undefined) delete process.env.LLM_BASE_URL; else process.env.LLM_BASE_URL = previous.base;
      if (previous.chatBase === undefined) delete process.env.CHAT_BASE_URL; else process.env.CHAT_BASE_URL = previous.chatBase;
    }
  });
});
