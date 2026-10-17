const axios = require('axios');
const { kbResponseSchema } = require('./schemas');

class KnowledgeBrainClient {
  constructor({ baseUrl = 'http://localhost:8000', timeoutMs = 30000, retries = 2 } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.timeoutMs = timeoutMs;
    this.retries = retries;
  }

  async ask(question) {
    let lastErr;
    for (let attempt = 0; attempt <= this.retries; attempt++) {
      try {
        const res = await axios.post(
          `${this.baseUrl}/ask`,
          { question },
          { timeout: this.timeoutMs }
        );
        return kbResponseSchema.parse(res.data);
      } catch (err) {
        lastErr = err;
        const status = err.response?.status;
        if (status === 400 || status === 422 || status === 429 || (status >= 500 && status < 600)) {
          if (attempt < this.retries) continue;
        }
        if (attempt < this.retries) continue;
        break;
      }
    }
    throw lastErr || new Error('knowledge brain request failed');
  }
}

module.exports = { KnowledgeBrainClient };
