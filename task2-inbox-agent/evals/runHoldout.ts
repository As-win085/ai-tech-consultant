import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import * as dotenv from 'dotenv';
import { LlmClassifier } from '../src/classifier';
import { Email } from '../src/types';
import { loadPricing, priceCost } from './pricing';

dotenv.config();

type Case = { id: string; subject: string; body: string; category: string; urgency: string; needsEscalation: boolean };
const DATA = path.resolve(__dirname, '../datasets/holdout-20.json');
const OUTPUT = path.resolve(__dirname, 'reports');
const PROVIDER = (process.env.LLM_PROVIDER ?? 'gemini').toLowerCase();
const MODELS = [
  { id: process.env.EVAL_MODEL_CHEAP ?? 'gemini-3.1-flash-lite', label: 'Lower-cost model' },
  { id: process.env.EVAL_MODEL_STRONG ?? 'gemini-3.8-flash', label: 'Stronger model' },
];
const BASE_URLS: Record<string, string> = {
  gemini: 'https://generativelanguage.googleapis.com/v1beta/openai',
  google: 'https://generativelanguage.googleapis.com/v1beta/openai',
  groq: 'https://api.groq.com/openai/v1', openrouter: 'https://openrouter.ai/api/v1',
  ollama: 'http://localhost:11434/v1', anthropic: 'https://api.anthropic.com/v1',
};

function reportFileName(modelId: string): string {
  return `holdout-20-${modelId.replace(/[^A-Za-z0-9_.-]/g, '_')}.json`;
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function percentile95(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted.length ? sorted[Math.max(0, Math.ceil(sorted.length * 0.95) - 1)] : 0;
}

function accuracy(expected: string[], actual: Array<string | null>): number {
  if (!expected.length) return 0;
  return expected.reduce((sum, value, i) => sum + Number(value === actual[i]), 0) / expected.length;
}

function macroF1(expected: string[], actual: Array<string | null>): number {
  const labels = [...new Set(expected)];
  const scores = labels.map((label) => {
    let tp = 0, fp = 0, fn = 0;
    expected.forEach((value, i) => {
      if (value === label && actual[i] === label) tp++;
      else if (value !== label && actual[i] === label) fp++;
      else if (value === label && actual[i] !== label) fn++;
    });
    return tp === 0 ? 0 : (2 * tp) / (2 * tp + fp + fn);
  });
  return scores.reduce((sum, score) => sum + score, 0) / (scores.length || 1);
}

async function main(): Promise<void> {
  const providerKey = PROVIDER === 'openrouter' ? process.env.OPENROUTER_API_KEY
    : PROVIDER === 'groq' ? process.env.GROQ_API_KEY
      : PROVIDER === 'gemini' || PROVIDER === 'google' ? process.env.GEMINI_API_KEY
        : PROVIDER === 'anthropic' ? process.env.ANTHROPIC_API_KEY : undefined;
  const apiKey = providerKey ?? process.env.LLM_API_KEY;
  const bytes = fs.readFileSync(DATA);
  const allCases = (JSON.parse(bytes.toString('utf8')) as { cases: Case[] }).cases;
  const requestedCaseIds = process.env.EVAL_CASE_IDS?.split(',').map((id) => id.trim()).filter(Boolean);
  const cases = requestedCaseIds ? allCases.filter((item) => requestedCaseIds.includes(item.id)) : allCases;
  const requestedModels = process.env.EVAL_MODELS?.split(',').map((id) => id.trim()).filter(Boolean);
  const modelsToRun = requestedModels ? MODELS.filter((model) => requestedModels.includes(model.id)) : MODELS;
  fs.mkdirSync(OUTPUT, { recursive: true });
  const comparisonRows: Array<Record<string, unknown>> = [];
  if (!apiKey) {
    const rulesPath = path.join(OUTPUT, 'holdout-20-rules-mock.json');
    const rules = JSON.parse(fs.readFileSync(rulesPath, 'utf8'));
    comparisonRows.push(...MODELS.map((model) => ({
      model: model.label, source: `${PROVIDER} API`, status: 'NOT RUN: LLM_API_KEY absent',
      category_accuracy: null, category_macro_f1: null, urgency_accuracy: null,
      escalation_precision: null, escalation_recall: null, median_latency_ms: null, p95_latency_ms: null,
      estimated_cost_usd: null, failures: null, failure_rate: null, retried_cases: null, retry_rate: null,
    })));
    comparisonRows.push({
      model: 'RuleBasedClassifier', source: 'offline deterministic rules baseline', status: 'measured',
      category_accuracy: rules.metrics.category_accuracy, category_macro_f1: rules.metrics.category_macro_f1,
      urgency_accuracy: rules.metrics.urgency_accuracy, escalation_precision: rules.metrics.escalation_precision,
      escalation_recall: rules.metrics.escalation_recall, median_latency_ms: rules.metrics.median_local_classifier_latency_ms,
      p95_latency_ms: rules.metrics.p95_local_classifier_latency_ms, estimated_cost_usd: null,
      failures: rules.metrics.failures, failure_rate: rules.metrics.failures / cases.length, retried_cases: 0, retry_rate: 0,
    });
    const comparisonPath = path.join(OUTPUT, 'comparison-holdout-20.json');
    fs.writeFileSync(comparisonPath, JSON.stringify({
      generated_at: new Date().toISOString(), dataset_sha256: createHash('sha256').update(bytes).digest('hex'),
      dataset_size: cases.length, note: `Provider deviation: configured default is ${PROVIDER}, not Claude. Model rows were not run; no per-case model results exist. Rule latency is local and not comparable to network latency.`, rows: comparisonRows,
    }, null, 2));
    console.log(`Model comparison (20 frozen emails; ${PROVIDER} rows not run)`);
    console.log('| Model | Status | Category acc. | Macro-F1 | Urgency acc. | Escalation P/R | Median / p95 ms | Cost USD | Failure / retry rate |');
    console.log('|---|---|---:|---:|---:|---:|---:|---:|---:|');
    for (const row of comparisonRows) {
      console.log(`| ${row.model} | ${row.status} | ${row.category_accuracy ?? '—'} | ${row.category_macro_f1 ?? '—'} | ${row.urgency_accuracy ?? '—'} | ${row.escalation_precision ?? '—'} / ${row.escalation_recall ?? '—'} | ${row.median_latency_ms ?? '—'} / ${row.p95_latency_ms ?? '—'} | ${row.estimated_cost_usd ?? '—'} | ${row.failure_rate ?? '—'} / ${row.retry_rate ?? '—'} |`);
    }
    console.log(`JSON comparison: ${comparisonPath}`);
    process.exitCode = 2;
    return;
  }
  const timeoutMs = Number.parseInt(process.env.LLM_TIMEOUT_MS ?? '60000', 10);
  const retries = Number.parseInt(process.env.LLM_RETRIES ?? '1', 10);

  for (const model of modelsToRun) {
    const priorPath = path.join(OUTPUT, reportFileName(model.id));
    const priorResults = requestedCaseIds && fs.existsSync(priorPath)
      ? (JSON.parse(fs.readFileSync(priorPath, 'utf8')).results as any[])
      : [];
    const resultById = new Map<string, any>(priorResults.map((result) => [result.id, {
      ...result,
      retry_count: Number(result.retry_count ?? Math.max(0, (result.attempts ?? 1) - 1)),
      model_failure: result.model_failure ?? Boolean(result.classification?.fallback),
      failed_http_responses: Number(result.failed_http_responses ?? 0),
      transport_failures: Number(result.transport_failures ?? 0),
      usage: { input_tokens: Number(result.usage?.input_tokens ?? 0), output_tokens: Number(result.usage?.output_tokens ?? 0) },
    }]));
    const freshResults: any[] = [];
    for (const item of cases) {
      const email: Email = { id: item.id, subject: item.subject, body: item.body } as Email;
      const calls: Array<{ raw: unknown; inputTokens: number; outputTokens: number; status: number }> = [];
      const transportErrors: Array<{ type: string; code: string | null }> = [];
      let fetchAttempts = 0;
      let transportFailures = 0;
      const captureFetch: typeof fetch = async (input, init) => {
        fetchAttempts++;
        let response: Response;
        try { response = await fetch(input, init); }
        catch (error) {
          transportFailures++;
          const transportError = error as Error & { cause?: { code?: unknown } };
          transportErrors.push({
            type: transportError?.name ?? 'UnknownError',
            code: typeof transportError?.cause?.code === 'string' ? transportError.cause.code : null,
          });
          throw error;
        }
        let raw: unknown = null;
        let inputTokens = 0, outputTokens = 0;
        try {
          const body = await response.clone().json() as any;
          raw = body;
          inputTokens = Number(body.usage?.input_tokens ?? body.usage?.prompt_tokens ?? 0);
          outputTokens = Number(body.usage?.output_tokens ?? body.usage?.completion_tokens ?? 0);
        } catch { /* retain status and transport failure without inventing response data */ }
        calls.push({ raw, inputTokens, outputTokens, status: response.status });
        return response;
      };
      const classifier = new LlmClassifier({
        provider: PROVIDER as any, model: model.id,
        baseUrl: process.env.LLM_BASE_URL ?? BASE_URLS[PROVIDER] ?? null, apiKey,
        timeoutMs, retries, fetchImpl: captureFetch,
      });
      const started = performance.now();
      const classification = await classifier.classify(email);
      const elapsedMs = Math.round((performance.now() - started) * 100) / 100;
      const successful = [...calls].reverse().find((call) => call.status >= 200 && call.status < 300);
      const rawText = (successful?.raw as any)?.content?.map((part: any) => part.text ?? '').join('') ??
        (successful?.raw as any)?.choices?.[0]?.message?.content ?? null;
      const failedCalls = calls.filter((call) => call.status < 200 || call.status >= 300).length;
      freshResults.push({
        id: item.id, input: item, expected: { category: item.category, urgency: item.urgency, needsEscalation: item.needsEscalation },
        raw_model_response: successful?.raw ?? calls.at(-1)?.raw ?? null,
        raw_attempts: calls.map((call) => ({ http_status: call.status, response: call.raw })),
        transport_errors: transportErrors,
        raw_model_text: rawText, classification, elapsed_ms: elapsedMs,
        attempts: fetchAttempts, did_retry: fetchAttempts > 1, transport_failures: transportFailures, failed_http_responses: failedCalls,
        retry_count: classifier.lastRetryCount, model_failure: classification.fallback,
        usage: { input_tokens: calls.reduce((n, call) => n + call.inputTokens, 0), output_tokens: calls.reduce((n, call) => n + call.outputTokens, 0) },
      });
      console.log(`${item.id}: ${classification.fallback ? 'FALLBACK' : 'classified'} (${elapsedMs} ms, ${fetchAttempts} attempt(s))`);
    }
    for (const result of freshResults) resultById.set(result.id, result);
    const results = allCases.map((item) => resultById.get(item.id)).filter(Boolean);
    const expectedCategory = results.map((result) => result.expected.category);
    const actualCategory = results.map((result) => result.classification.fallback ? null : result.classification.category);
    const expectedUrgency = results.map((result) => result.expected.urgency);
    const actualUrgency = results.map((result) => result.classification.fallback ? null : result.classification.urgency);
    const expectedEscalation = results.map((result) => String(result.expected.needsEscalation));
    const actualEscalation = results.map((result) => result.classification.fallback ? null : String(result.classification.needsEscalation));
    const tp = results.filter((r) => r.classification.needsEscalation && r.expected.needsEscalation).length;
    const fp = results.filter((r) => r.classification.needsEscalation && !r.expected.needsEscalation).length;
    const fn = results.filter((r) => !r.classification.needsEscalation && r.expected.needsEscalation).length;
    const inputTokens = results.reduce((sum, row) => sum + row.usage.input_tokens, 0);
    const outputTokens = results.reduce((sum, row) => sum + row.usage.output_tokens, 0);
    const pricing = loadPricing();
    const { costUsd: totalCost, basis: costBasis } = priceCost(pricing, model.id, inputTokens, outputTokens);
    const failureCount = results.filter((row) => row.classification.fallback).length;
    const retryCount = results.filter((row) => row.did_retry).length;
    const latencies = results.map((row) => row.elapsed_ms);
    const report = {
      generated_at: new Date().toISOString(), dataset: path.basename(DATA), dataset_sha256: createHash('sha256').update(bytes).digest('hex'),
      dataset_size: allCases.length, model: model.id, model_label: model.label, provider: PROVIDER, source_mode: 'live API',
      merged_prior_results: Boolean(requestedCaseIds), rerun_case_ids: requestedCaseIds ?? null,
      thresholds: 'No pass threshold; descriptive metrics on this fixed synthetic holdout.',
      metrics: {
        category_accuracy: accuracy(expectedCategory, actualCategory), category_macro_f1: macroF1(expectedCategory, actualCategory),
        urgency_accuracy: accuracy(expectedUrgency, actualUrgency), escalation_accuracy: accuracy(expectedEscalation, actualEscalation),
        escalation_precision: tp + fp ? tp / (tp + fp) : 0, escalation_recall: tp + fn ? tp / (tp + fn) : 0,
        median_latency_ms: median(latencies), p95_latency_ms: percentile95(latencies),
        failures: failureCount, failure_rate: failureCount / results.length,
        retried_cases: retryCount, retry_rate: retryCount / results.length,
        retry_attempts_total: results.reduce((sum, row) => sum + row.retry_count, 0),
        http_failures: results.reduce((sum, row) => sum + row.failed_http_responses, 0),
        transport_failures: results.reduce((sum, row) => sum + row.transport_failures, 0),
        input_tokens: inputTokens, output_tokens: outputTokens, estimated_cost_usd: totalCost,
        cost_basis: costBasis,
        pricing_table: 'shared-docs/evals/pricing.json',
        pricing_source: pricing?.source ?? null,
        pricing_retrieved_at: pricing?.retrieved_at ?? null,
      }, results,
    };
    const target = path.join(OUTPUT, reportFileName(model.id));
    fs.writeFileSync(target, JSON.stringify(report, null, 2));
    comparisonRows.push({ model: model.label, source: `live ${PROVIDER} API`, ...report.metrics });
    console.log(`${model.id}: category accuracy=${report.metrics.category_accuracy}, urgency accuracy=${report.metrics.urgency_accuracy}, escalation precision=${report.metrics.escalation_precision}, recall=${report.metrics.escalation_recall}, median latency=${report.metrics.median_latency_ms} ms, p95=${report.metrics.p95_latency_ms} ms, failures=${report.metrics.failures}, retry rate=${report.metrics.retry_rate}, estimated cost=${totalCost === null ? 'not estimated' : `$${totalCost.toFixed(6)}`}; report=${target}`);
  }
  for (const model of MODELS) {
    if (modelsToRun.includes(model)) continue;
    if (model.id === 'gemini-3.8-flash') {
      comparisonRows.push({
        model: model.id, source: 'not selected for this run',
        status: 'not evaluated in this run', category_accuracy: null, category_macro_f1: null,
        urgency_accuracy: null, escalation_precision: null, escalation_recall: null,
        median_latency_ms: null, p95_latency_ms: null, estimated_cost_usd: null,
        failures: null, failure_rate: null, retried_cases: null, retry_rate: null,
      });
      continue;
    }
    const priorPath = path.join(OUTPUT, reportFileName(model.id));
    if (fs.existsSync(priorPath)) {
      const prior = JSON.parse(fs.readFileSync(priorPath, 'utf8'));
      comparisonRows.push({ model: model.label, source: `live ${PROVIDER} API`, ...prior.metrics });
    }
  }
  const rulesPath = path.join(OUTPUT, 'holdout-20-rules-mock.json');
  const rules = JSON.parse(fs.readFileSync(rulesPath, 'utf8'));
  comparisonRows.push({
    model: 'RuleBasedClassifier', source: 'offline deterministic rules baseline',
    category_accuracy: rules.metrics.category_accuracy, category_macro_f1: rules.metrics.category_macro_f1,
    urgency_accuracy: rules.metrics.urgency_accuracy, escalation_precision: rules.metrics.escalation_precision,
    escalation_recall: rules.metrics.escalation_recall, median_latency_ms: rules.metrics.median_local_classifier_latency_ms,
    p95_latency_ms: rules.metrics.p95_local_classifier_latency_ms ?? null,
    estimated_cost_usd: null, failures: 0, failure_rate: 0, retried_cases: 0, retry_rate: 0,
  });
  const comparisonPath = path.join(OUTPUT, 'comparison-holdout-20.json');
  fs.writeFileSync(comparisonPath, JSON.stringify({
    generated_at: new Date().toISOString(), dataset_sha256: createHash('sha256').update(bytes).digest('hex'),
    note: 'Provider/model selection, pricing source, and costs are from this run. Pricing comes from shared-docs/evals/pricing.json (constant table with source and retrieval date). Set LLM_PROVIDER, LLM_BASE_URL, provider-specific key (OPENROUTER_API_KEY or GROQ_API_KEY), EVAL_MODEL_CHEAP and EVAL_MODEL_STRONG to select provider/models. Rule latency is local and not comparable to network latency. Partial reruns merge only named cases with earlier raw case results.', rows: comparisonRows,
  }, null, 2));
  console.log('\nModel comparison (20 fixed synthetic emails)');
  console.log('| Model | Source | Category acc. | Macro-F1 | Urgency acc. | Escalation P/R | Median / p95 ms | Cost USD | Failure / retry rate |');
  console.log('|---|---|---:|---:|---:|---:|---:|---:|---:|');
  for (const row of comparisonRows) {
    console.log(`| ${row.model} | ${row.source} | ${row.category_accuracy ?? '—'} | ${row.category_macro_f1 ?? '—'} | ${row.urgency_accuracy ?? '—'} | ${row.escalation_precision ?? '—'} / ${row.escalation_recall ?? '—'} | ${row.median_latency_ms ?? '—'} / ${row.p95_latency_ms ?? '—'} | ${row.estimated_cost_usd ?? '—'} | ${row.failure_rate ?? '—'} / ${row.retry_rate ?? '—'} |`);
  }
  console.log(`JSON comparison: ${comparisonPath}`);
}

main().catch((error) => { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; });
