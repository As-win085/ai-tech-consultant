import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import { LlmClassifier } from '../src/classifier';
import { loadConfig } from '../src/config';
import { Email } from '../src/types';

type Case = { id: string; subject: string; body: string; category: string; urgency: string; needsEscalation: boolean };
const DATA = path.resolve(__dirname, '../datasets/holdout-20.json');
const OUTPUT = path.resolve(__dirname, 'reports');
const MODELS = [
  { id: 'claude-sonnet-5', inputPerMillion: 2, outputPerMillion: 10 },
  { id: 'claude-haiku-4-5-20251001', inputPerMillion: 1, outputPerMillion: 5 },
];

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
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
  const config = loadConfig();
  const apiKey = process.env.ANTHROPIC_API_KEY ?? (config.llmProvider === 'anthropic' ? process.env.LLM_API_KEY : undefined);
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY is required (or LLM_API_KEY with LLM_PROVIDER=anthropic); no requests were sent.');
  const bytes = fs.readFileSync(DATA);
  const cases = (JSON.parse(bytes.toString('utf8')) as { cases: Case[] }).cases;
  fs.mkdirSync(OUTPUT, { recursive: true });

  for (const model of MODELS) {
    const results: any[] = [];
    for (const item of cases) {
      const email: Email = { subject: item.subject, body: item.body } as Email;
      const calls: Array<{ raw: unknown; inputTokens: number; outputTokens: number; status: number }> = [];
      let fetchAttempts = 0;
      let transportFailures = 0;
      const captureFetch: typeof fetch = async (input, init) => {
        fetchAttempts++;
        let response: Response;
        try { response = await fetch(input, init); }
        catch (error) { transportFailures++; throw error; }
        let raw: unknown = null;
        let inputTokens = 0, outputTokens = 0;
        try {
          const body = await response.clone().json() as any;
          raw = body;
          inputTokens = Number(body.usage?.input_tokens ?? 0);
          outputTokens = Number(body.usage?.output_tokens ?? 0);
        } catch { /* retain status and transport failure without inventing response data */ }
        calls.push({ raw, inputTokens, outputTokens, status: response.status });
        return response;
      };
      const classifier = new LlmClassifier({
        provider: 'anthropic', model: model.id, baseUrl: null, apiKey: config.llmApiKey,
        timeoutMs: config.llmTimeoutMs, retries: config.llmRetries, fetchImpl: captureFetch,
      });
      const started = performance.now();
      const classification = await classifier.classify(email);
      const elapsedMs = Math.round((performance.now() - started) * 100) / 100;
      const successful = [...calls].reverse().find((call) => call.status >= 200 && call.status < 300);
      const rawText = (successful?.raw as any)?.content?.map((part: any) => part.text ?? '').join('') ?? null;
      const failedCalls = calls.filter((call) => call.status < 200 || call.status >= 300).length;
      results.push({
        id: item.id, input: item, expected: { category: item.category, urgency: item.urgency, needsEscalation: item.needsEscalation },
        raw_model_response: successful?.raw ?? calls.at(-1)?.raw ?? null,
        raw_model_text: rawText, classification, elapsed_ms: elapsedMs,
        attempts: fetchAttempts, transport_failures: transportFailures, failed_http_responses: failedCalls,
        usage: { input_tokens: calls.reduce((n, call) => n + call.inputTokens, 0), output_tokens: calls.reduce((n, call) => n + call.outputTokens, 0) },
      });
      console.log(`${item.id}: ${classification.fallback ? 'FALLBACK' : 'classified'} (${elapsedMs} ms, ${calls.length} attempt(s))`);
    }
    const expectedCategory = cases.map((item) => item.category);
    const actualCategory = results.map((result) => result.classification.fallback ? null : result.classification.category);
    const expectedUrgency = cases.map((item) => item.urgency);
    const actualUrgency = results.map((result) => result.classification.fallback ? null : result.classification.urgency);
    const expectedEscalation = cases.map((item) => String(item.needsEscalation));
    const actualEscalation = results.map((result) => result.classification.fallback ? null : String(result.classification.needsEscalation));
    const tp = results.filter((r) => r.classification.needsEscalation && r.expected.needsEscalation).length;
    const fp = results.filter((r) => r.classification.needsEscalation && !r.expected.needsEscalation).length;
    const fn = results.filter((r) => !r.classification.needsEscalation && r.expected.needsEscalation).length;
    const inputTokens = results.reduce((sum, row) => sum + row.usage.input_tokens, 0);
    const outputTokens = results.reduce((sum, row) => sum + row.usage.output_tokens, 0);
    const totalCost = (inputTokens * model.inputPerMillion + outputTokens * model.outputPerMillion) / 1_000_000;
    const report = {
      generated_at: new Date().toISOString(), dataset: path.basename(DATA), dataset_sha256: createHash('sha256').update(bytes).digest('hex'),
      dataset_size: cases.length, model: model.id, provider: 'Anthropic Messages API', source_mode: 'live API',
      thresholds: 'No pass threshold; descriptive metrics on this fixed synthetic holdout.',
      metrics: {
        category_accuracy: accuracy(expectedCategory, actualCategory), category_macro_f1: macroF1(expectedCategory, actualCategory),
        urgency_accuracy: accuracy(expectedUrgency, actualUrgency), escalation_accuracy: accuracy(expectedEscalation, actualEscalation),
        escalation_precision: tp + fp ? tp / (tp + fp) : 0, escalation_recall: tp + fn ? tp / (tp + fn) : 0,
        median_latency_ms: median(results.map((row) => row.elapsed_ms)), failures: results.filter((row) => row.classification.fallback).length,
        http_failures: results.reduce((sum, row) => sum + row.failed_http_responses, 0),
        transport_failures: results.reduce((sum, row) => sum + row.transport_failures, 0),
        input_tokens: inputTokens, output_tokens: outputTokens, estimated_cost_usd: totalCost,
        cost_basis: `Anthropic published list rates: input $${model.inputPerMillion}/MTok and output $${model.outputPerMillion}/MTok; estimate from reported usage, not invoice.`
      }, results,
    };
    const target = path.join(OUTPUT, `holdout-20-${model.id}.json`);
    fs.writeFileSync(target, JSON.stringify(report, null, 2));
    console.log(`${model.id}: category accuracy=${report.metrics.category_accuracy}, urgency accuracy=${report.metrics.urgency_accuracy}, escalation precision=${report.metrics.escalation_precision}, recall=${report.metrics.escalation_recall}, median latency=${report.metrics.median_latency_ms} ms, failures=${report.metrics.failures}, estimated cost=$${totalCost.toFixed(6)}; report=${target}`);
  }
}

main().catch((error) => { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; });
