import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import { RuleBasedClassifier } from '../src/classifier';
import { Email } from '../src/types';

type Case = { id: string; subject: string; body: string; category: string; urgency: string; needsEscalation: boolean };
const DATA = path.resolve(__dirname, '../datasets/holdout-20.json');
const OUTPUT = path.resolve(__dirname, 'reports/holdout-20-rules-mock.json');

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function accuracy(expected: unknown[], actual: unknown[]): number {
  return expected.length ? expected.filter((value, index) => value === actual[index]).length / expected.length : 0;
}

async function main(): Promise<void> {
  const bytes = fs.readFileSync(DATA);
  const cases = (JSON.parse(bytes.toString('utf8')) as { cases: Case[] }).cases;
  const classifier = new RuleBasedClassifier();
  const results = await Promise.all(cases.map(async (item) => {
    const email: Email = {
      id: item.id, from: 'customer@example.test', to: ['support@example.test'], subject: item.subject,
      body: item.body, receivedAt: '2026-10-18T00:00:00.000Z', threadId: null,
    };
    const started = performance.now();
    const classification = await classifier.classify(email);
    const elapsedMs = Math.round((performance.now() - started) * 100) / 100;
    return { id: item.id, input: item, expected: { category: item.category, urgency: item.urgency, needsEscalation: item.needsEscalation }, raw_model_response: null, classification, elapsed_ms: elapsedMs };
  }));
  const expectedCategories = cases.map((item) => item.category);
  const predictedCategories = results.map((item) => item.classification.category);
  const labels = [...new Set(expectedCategories)];
  const macroF1 = labels.reduce((total, label) => {
    const tp = results.filter((item) => item.expected.category === label && item.classification.category === label).length;
    const fp = results.filter((item) => item.expected.category !== label && item.classification.category === label).length;
    const fn = results.filter((item) => item.expected.category === label && item.classification.category !== label).length;
    return total + (tp ? (2 * tp) / (2 * tp + fp + fn) : 0);
  }, 0) / (labels.length || 1);
  const tp = results.filter((item) => item.expected.needsEscalation && item.classification.needsEscalation).length;
  const fp = results.filter((item) => !item.expected.needsEscalation && item.classification.needsEscalation).length;
  const fn = results.filter((item) => item.expected.needsEscalation && !item.classification.needsEscalation).length;
  const report = {
    generated_at: new Date().toISOString(), dataset: path.basename(DATA), dataset_sha256: createHash('sha256').update(bytes).digest('hex'),
    dataset_size: cases.length, model: null, provider: null, source_mode: 'offline deterministic RuleBasedClassifier; no mocked or live LLM response',
    metrics: {
      category_accuracy: accuracy(expectedCategories, predictedCategories), category_macro_f1: macroF1,
      urgency_accuracy: accuracy(cases.map((item) => item.urgency), results.map((item) => item.classification.urgency)),
      escalation_accuracy: accuracy(cases.map((item) => item.needsEscalation), results.map((item) => item.classification.needsEscalation)),
      escalation_precision: tp + fp ? tp / (tp + fp) : 0, escalation_recall: tp + fn ? tp / (tp + fn) : 0,
      median_local_classifier_latency_ms: median(results.map((item) => item.elapsed_ms)), estimated_cost_usd: null,
      failures: 0, note: 'Rules baseline only; these metrics are not Claude model measurements.',
    }, results,
  };
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ source_mode: report.source_mode, dataset_size: cases.length, metrics: report.metrics, report: OUTPUT }, null, 2));
}

main().catch((error) => { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; });
