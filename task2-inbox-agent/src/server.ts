import Fastify, { FastifyInstance } from 'fastify';
import { ZodError } from 'zod';
import { AppConfig, loadConfig } from './config';
import { InboxAgent } from './agent';
import { InvalidTransitionError } from './review';
import { KnowledgeBrainError } from './kbClient';
import { ingestRequestSchema, reviewActionSchema } from './schemas';
import { reviewUiHtml } from './ui';
import { createAgentBundle } from './factory';

const VERSION = '0.1.0';

export interface ServerDeps {
  agent: InboxAgent;
  config: AppConfig;
}

export function buildServer(deps: ServerDeps): FastifyInstance {
  const { agent, config } = deps;
  const app = Fastify({
    logger: config.logLevel === 'silent' ? false : { level: config.logLevel },
  });

  app.setErrorHandler((error, request, reply) => {
    const requestId = request.id;
    let status = 500;
    let code = 'internal_error';
    let message = 'Internal server error';

    if (error instanceof ZodError) {
      status = 400;
      code = 'validation_error';
      message = error.issues.map((i) => `${i.path.join('.') || 'body'}: ${i.message}`).join('; ');
    } else if (error instanceof InvalidTransitionError) {
      status = 409;
      code = 'invalid_transition';
      message = error.message;
    } else if (error instanceof KnowledgeBrainError) {
      status = error.kind === 'timeout' ? 504 : 502;
      code = `knowledge_brain_${error.kind}`;
      message = error.message;
    } else if (error.message && /not found/.test(error.message)) {
      status = 404;
      code = 'not_found';
      message = error.message;
    } else if (error.message && /requires/.test(error.message)) {
      status = 400;
      code = 'invalid_request';
      message = error.message;
    } else if (typeof (error as { statusCode?: number }).statusCode === 'number') {
      const sc = (error as { statusCode?: number }).statusCode as number;
      if (sc >= 400 && sc < 500) {
        status = sc;
        code = 'bad_request';
        message = error.message;
      }
    }

    if (status >= 500) {
      request.log.error({ err: error }, 'request failed');
    }
    reply.status(status).send({ error: { code, message, request_id: requestId } });
  });

  app.get('/', async (_req, reply) => {
    reply.type('text/html').send(reviewUiHtml);
  });

  app.get('/health', async () => ({ status: 'ok', version: VERSION, service: 'inbox-agent' }));

  app.get('/ready', async () => {
    const automation = await agent.getAutomationState();
    const knowledgeBrainReachable = await agent.kbReachable();
    return {
      status: knowledgeBrainReachable ? 'ready' : 'degraded',
      store: 'configured',
      knowledgeBrain: { reachable: knowledgeBrainReachable },
      automation,
    };
  });

  app.post('/emails', async (req, reply) => {
    const body = ingestRequestSchema.parse(req.body);
    const items = await agent.ingestEmails(body.emails as never);
    reply.status(201);
    return { ingested: items.length, items: items.map((i) => i.id) };
  });

  app.get('/emails', async (req) => {
    const q = req.query as { state?: string; category?: string };
    const items = await agent.listItems({
      state: q.state as never,
      category: q.category as never,
    });
    return { count: items.length, items };
  });

  app.get('/emails/:id', async (req) => {
    const { id } = req.params as { id: string };
    const item = await agent.getItem(id);
    if (!item) throw new Error(`item not found: ${id}`);
    return item;
  });

  app.post('/emails/:id/draft', async (req) => {
    const { id } = req.params as { id: string };
    const item = await agent.generateDraft(id);
    return item;
  });

  app.post('/emails/:id/review', async (req) => {
    const { id } = req.params as { id: string };
    const action = reviewActionSchema.parse(req.body ?? {});
    const result = await agent.review(id, action);
    return {
      item: result.item,
      feedback: result.feedback,
      automation: result.automationState,
      automationExcluded: result.automationExcluded,
      automationExclusionReasons: result.automationExclusionReasons,
    };
  });

  app.get('/emails/:id/audit', async (req) => {
    const { id } = req.params as { id: string };
    const audit = await agent.getAudit(id);
    return { count: audit.length, audit };
  });

  app.get('/feedback', async (req) => {
    const q = req.query as { itemId?: string };
    const feedback = await agent.getFeedback(q.itemId);
    return { count: feedback.length, feedback };
  });

  app.get('/stats', async () => {
    const automation = await agent.getAutomationState();
    const items = await agent.listItems();
    const byCategory: Record<string, number> = {};
    const byState: Record<string, number> = {};
    for (const item of items) {
      byCategory[item.classification.category] = (byCategory[item.classification.category] ?? 0) + 1;
      byState[item.state] = (byState[item.state] ?? 0) + 1;
    }
    return {
      total: items.length,
      byCategory,
      byState,
      automation: { ...automation, threshold: config.maxConsecutiveUneditedApprovals },
    };
  });

  return app;
}

async function start(): Promise<void> {
  const config = loadConfig();
  const { agent, storeKind } = await createAgentBundle(config);
  const app = buildServer({ agent, config });

  if (config.datasetPath) {
    try {
      const { loaded } = await agent.loadDataset(config.datasetPath);
      app.log.info({ loaded, dataset: config.datasetPath }, 'dataset loaded');
    } catch (err) {
      app.log.warn({ err, dataset: config.datasetPath }, 'dataset not loaded');
    }
  }

  await app.listen({ port: config.port, host: '0.0.0.0' });
  app.log.info({ port: config.port, store: storeKind, classifier: config.classifier }, 'inbox-agent started');
}

if (require.main === module) {
  start().catch((err) => {
    // eslint-disable-next-line no-console
    console.error('failed to start inbox-agent:', err);
    process.exit(1);
  });
}
