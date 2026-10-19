import { loadConfig } from '../src/config';

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
