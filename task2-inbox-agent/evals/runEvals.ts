/* eslint-disable no-console */
import { readFileSync, writeFileSync } from 'fs';
import { resolve } from 'path';
import { Classifier, LlmClassifier, RuleBasedClassifier, buildClassifier as makeClassifier } from '../src/classifier';
import { InboxAgent } from '../src/agent';
import { InMemoryStore } from '../src/store';
import { KnowledgeBrainError } from '../src/kbClient';
import { loadConfig } from '../src/config';
import { CATEGORIES, Category, Classification, Email, KbAnswer } from '../src/types';
import { MockKbClient } from '../tests/helpers';
import { loadPricing, priceCost } from './pricing';

interface ClassificationCase {
  id: string;
  email: { from: string; subject: string; body: string };
  expect: { category: Category; urgency: string; escalate: boolean; riskFlags?: string[] };
}
interface DraftCase {
  id: string;
  email: { from: string; subject: string; body: string };
  kb: Record<string, unknown>;
  expect: { grounded?: boolean; minCitations?: number; escalationReason?: boolean };
}
interface SafetyCase {
  id: string;
  email: { from: string; subject: string; body: string };
  kb?: { error: string };
  llmMalformed?: boolean;
  expect: { mustNotAnswer?: boolean; degraded?: boolean; escalate?: boolean; classifierFallback?: boolean };
}
interface ReviewCase {
  id: string;
  email: { from: string; subject: string; body: string };
  kb: Record<string, unknown>;
  actions: Array<{ action: string; editedDraft?: string; rejectionReason?: string; escalationReason?: string }>;
  expect: {
    state: string;
    outcomes: string[];
    counter?: number;
    automationEligible?: boolean;
    automationExcluded?: boolean;
    rejectReason?: string;
    secondActionRejected?: boolean;
  };
}

interface EvalCaseFile {
  version: number;
  scoring: { passThresholds: Record<string, number> };
  classificationCases: ClassificationCase[];
  draftCases: DraftCase[];
  safetyCases: SafetyCase[];
  reviewCases: ReviewCase[];
}

const args = process.argv.slice(2);
const useLlm = args.includes('--classifier=llm');
const skipDataset = args.includes('--no-dataset');
const jsonOnly = args.includes('--json');

function buildEmail(e: { from: string; subject: string; body: string }, id: string): Email {
  return {
    id,
    from: e.from,
    to: ['support@supportflow.example'],
    subject: e.subject,
    body: e.body,
    receivedAt: '2026-01-01T00:00:00.000Z',
    threadId: null,
  };
}

function makeKbResponse(kb: Record<string, unknown>): KbAnswer {
  return {
    answer: (kb.answer as string) ?? '',
    citations: (kb.citations as KbAnswer['citations']) ?? [],
    evidence_status: (kb.evidence_status as string) ?? 'insufficient',
    needs_escalation: !!kb.needs_escalation,
    escalation_reason: (kb.escalation_reason as string) ?? null,
    request_id: (kb.request_id as string) ?? 'eval',
    model: 'eval',
  };
}

const usageTotals = { input_tokens: 0, output_tokens: 0 };

function capturingFetch(): typeof fetch {
  return (async (input: Parameters<typeof fetch>[0], init?: Parameters<typeof fetch>[1]) => {
    const response = await fetch(input, init);
    try {
      const body = await response.clone().json() as { usage?: { input_tokens?: unknown; output_tokens?: unknown; prompt_tokens?: unknown; completion_tokens?: unknown } };
      usageTotals.input_tokens += Number(body?.usage?.input_tokens ?? body?.usage?.prompt_tokens ?? 0);
      usageTotals.output_tokens += Number(body?.usage?.output_tokens ?? body?.usage?.completion_tokens ?? 0);
    } catch { /* non-JSON response; classifier handles status and fallback */ }
    return response;
  }) as typeof fetch;
}

function selectClassifier(): Classifier {
  if (!useLlm) return new RuleBasedClassifier();
  const config = loadConfig();
  return makeClassifier('llm', {
    provider: config.llmProvider,
    model: config.llmModel,
    baseUrl: config.llmBaseUrl,
    apiKey: config.llmApiKey,
    timeoutMs: config.llmTimeoutMs,
    retries: config.llmRetries,
    fetchImpl: capturingFetch(),
  });
}

async function classifyWith(classifier: Classifier, emails: Array<{ email: Email; expected: { category: Category; urgency: string; escalate: boolean } }>) {
  const results: Array<{ expected: typeof emails[number]['expected']; predicted: Classification }> = [];
  for (const { email, expected } of emails) {
    const predicted = await classifier.classify(email);
    results.push({ expected, predicted });
  }
  return results;
}

function macroF1(pairs: Array<{ actual: Category; predicted: Category }>) {
  const labels = CATEGORIES;
  let f1sum = 0;
  let counted = 0;
  for (const label of labels) {
    let tp = 0, fp = 0, fn = 0;
    for (const p of pairs) {
      if (p.predicted === label && p.actual === label) tp++;
      else if (p.predicted === label && p.actual !== label) fp++;
      else if (p.predicted !== label && p.actual === label) fn++;
    }
    if (tp + fp + fn === 0) continue;
    const precision = tp + fp === 0 ? 0 : tp / (tp + fp);
    const recall = tp + fn === 0 ? 0 : tp / (tp + fn);
    const f1 = precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall);
    f1sum += f1;
    counted++;
  }
  return counted === 0 ? 0 : f1sum / counted;
}

async function main() {
  const caseFile: EvalCaseFile = JSON.parse(readFileSync(resolve(__dirname, 'cases.json'), 'utf8'));
  const classifier = selectClassifier();
  const report: Record<string, unknown> = {
    generatedAt: new Date().toISOString(),
    classifier: classifier.name,
    host: { platform: process.platform, node: process.version },
    thresholds: caseFile.scoring.passThresholds,
  };

  // ---------- classification ----------
  const clsInputs: Array<{ email: Email; expected: { category: Category; urgency: string; escalate: boolean } }> = [];
  caseFile.classificationCases.forEach((c, i) => {
    clsInputs.push({ email: buildEmail(c.email, c.id || `cls-${i}`), expected: c.expect });
  });
  if (!skipDataset) {
    const dataset = JSON.parse(readFileSync(resolve(__dirname, '..', 'datasets', 'emails-sample.json'), 'utf8'));
    for (const e of dataset.emails) {
      if (!e.expected) continue;
      clsInputs.push({
        email: buildEmail(e, e.id),
        expected: { category: e.expected.category, urgency: e.expected.urgency, escalate: e.expected.escalate },
      });
    }
  }
  const clsResults = await classifyWith(classifier, clsInputs);
  const catPairs = clsResults.map((r) => ({ actual: r.expected.category, predicted: r.predicted.category }));
  const categoryAccuracy = catPairs.filter((p) => p.actual === p.predicted).length / (catPairs.length || 1);
  const urgencyAccuracy = clsResults.filter((r) => r.expected.urgency === r.predicted.urgency).length / (clsResults.length || 1);
  const expectedEsc = clsResults.filter((r) => r.expected.escalate);
  const escalationRecall = expectedEsc.length ? expectedEsc.filter((r) => r.predicted.needsEscalation).length / expectedEsc.length : 1;
  const predictedEsc = clsResults.filter((r) => r.predicted.needsEscalation);
  const escalationPrecision = predictedEsc.length ? predictedEsc.filter((r) => r.expected.escalate).length / predictedEsc.length : 1;
  const f1 = macroF1(catPairs);
  report.classification = {
    cases: clsResults.length,
    categoryAccuracy: round(categoryAccuracy),
    urgencyAccuracy: round(urgencyAccuracy),
    macroF1: round(f1),
    escalationRecall: round(escalationRecall),
    escalationPrecision: round(escalationPrecision),
  };

  // ---------- drafts ----------
  const draftResults: Array<{ id: string; pass: boolean; detail: string }> = [];
  for (const c of caseFile.draftCases) {
    const email = buildEmail(c.email, c.id);
    const agent = new InboxAgent({
      store: new InMemoryStore(),
      classifier: new RuleBasedClassifier(),
      kbClient: new MockKbClient([makeKbResponse(c.kb)]),
    });
    const [item] = await agent.ingestEmails([{ ...email } as never]);
    const updated = await agent.generateDraft(item.id);
    const d = updated.draft!;
    let pass = true;
    const details: string[] = [];
    if (c.expect.grounded !== undefined && d.grounded !== c.expect.grounded) { pass = false; details.push(`grounded=${d.grounded} expected=${c.expect.grounded}`); }
    if (c.expect.minCitations !== undefined && d.citations.length < c.expect.minCitations) { pass = false; details.push(`citations=${d.citations.length} < ${c.expect.minCitations}`); }
    if (c.expect.escalationReason && !d.escalationReason) { pass = false; details.push('missing escalationReason'); }
    draftResults.push({ id: c.id, pass, detail: details.join('; ') || 'ok' });
  }
  report.drafts = { cases: draftResults.length, passed: draftResults.filter((r) => r.pass).length, results: draftResults };

  // ---------- safety ----------
  const safetyResults: Array<{ id: string; pass: boolean; detail: string }> = [];
  for (const c of caseFile.safetyCases) {
    const email = buildEmail(c.email, c.id);
    let pass = true;
    const details: string[] = [];
    if (c.llmMalformed) {
      const llm = new LlmClassifier({
        provider: 'openai_compatible',
        model: 'eval-malformed',
        baseUrl: 'http://localhost:1',
        apiKey: null,
        timeoutMs: 500,
        retries: 1,
        fetchImpl: (async () => ({ ok: true, status: 200, json: async () => ({ choices: [{ message: { content: 'not json' } }] }) }) as unknown as Response) as unknown as typeof fetch,
      });
      const result = await llm.classify(email);
      if (c.expect.classifierFallback && !result.fallback) { pass = false; details.push('classifier did not fall back'); }
      if (c.expect.escalate && !result.needsEscalation) { pass = false; details.push('did not escalate'); }
    } else if (c.kb && c.kb.error) {
      const agent = new InboxAgent({
        store: new InMemoryStore(),
        classifier: new RuleBasedClassifier(),
        kbClient: new MockKbClient(() => {
          throw new KnowledgeBrainError(c.kb!.error as never, `simulated ${c.kb!.error}`);
        }),
      });
      const [item] = await agent.ingestEmails([{ ...email } as never]);
      const updated = await agent.generateDraft(item.id);
      const d = updated.draft!;
      if (c.expect.mustNotAnswer && (d.grounded || d.citations.length > 0)) { pass = false; details.push('fabricated an answer'); }
      if (c.expect.degraded && !updated.metadata.kbError) { pass = false; details.push('failure not surfaced'); }
      if (c.expect.escalate && !d.escalationReason) { pass = false; details.push('no escalation reason'); }
    }
    safetyResults.push({ id: c.id, pass, detail: details.join('; ') || 'ok' });
  }
  const noFabrication = safetyResults.filter((r) => r.pass).length / (safetyResults.length || 1);
  report.safety = { cases: safetyResults.length, passed: safetyResults.filter((r) => r.pass).length, noFabrication: round(noFabrication), results: safetyResults };

  // ---------- review ----------
  const reviewResults: Array<{ id: string; pass: boolean; detail: string }> = [];
  for (const c of caseFile.reviewCases) {
    const email = buildEmail(c.email, c.id);
    const agent = new InboxAgent({
      store: new InMemoryStore(),
      classifier: new RuleBasedClassifier(),
      kbClient: new MockKbClient([makeKbResponse(c.kb)]),
    });
    const [item] = await agent.ingestEmails([{ ...email } as never]);
    await agent.generateDraft(item.id);
    let pass = true;
    const details: string[] = [];
    const outcomes: string[] = [];
    let lastResult: Awaited<ReturnType<typeof agent.review>> | null = null;
    for (let i = 0; i < c.actions.length; i++) {
      const action = c.actions[i];
      try {
        lastResult = await agent.review(item.id, action as never);
        outcomes.push(lastResult.feedback.outcome);
      } catch (err) {
        if (i > 0 && c.expect.secondActionRejected) {
          // expected rejection
        } else {
          pass = false;
          details.push(`action ${action.action} threw: ${(err as Error).message}`);
        }
      }
    }
    const finalItem = await agent.getItem(item.id);
    if (finalItem?.state !== c.expect.state) { pass = false; details.push(`state=${finalItem?.state} expected=${c.expect.state}`); }
    if (JSON.stringify(outcomes) !== JSON.stringify(c.expect.outcomes)) { pass = false; details.push(`outcomes=${outcomes.join(',')} expected=${c.expect.outcomes.join(',')}`); }
    const automation = await agent.getAutomationState();
    if (c.expect.counter !== undefined && automation.consecutiveUneditedApprovals !== c.expect.counter) { pass = false; details.push(`counter=${automation.consecutiveUneditedApprovals} expected=${c.expect.counter}`); }
    if (c.expect.automationEligible !== undefined && automation.automationEligible !== c.expect.automationEligible) { pass = false; details.push(`automationEligible=${automation.automationEligible}`); }
    if (c.expect.automationExcluded !== undefined && lastResult && lastResult.automationExcluded !== c.expect.automationExcluded) { pass = false; details.push(`automationExcluded=${lastResult.automationExcluded}`); }
    if (c.expect.rejectReason) {
      const fb = await agent.getFeedback(item.id);
      if (!fb.some((f) => f.reason === c.expect.rejectReason)) { pass = false; details.push('reject reason not recorded'); }
    }
    reviewResults.push({ id: c.id, pass, detail: details.join('; ') || 'ok' });
  }
  const reviewCorrectness = reviewResults.filter((r) => r.pass).length / (reviewResults.length || 1);
  report.review = { cases: reviewResults.length, passed: reviewResults.filter((r) => r.pass).length, correctness: round(reviewCorrectness), results: reviewResults };

  // ---------- thresholds ----------
  const t = caseFile.scoring.passThresholds;
  const checks: Record<string, { value: number; threshold: number; pass: boolean }> = {
    categoryAccuracy: { value: categoryAccuracy, threshold: t.categoryAccuracy, pass: categoryAccuracy >= t.categoryAccuracy },
    escalationRecall: { value: escalationRecall, threshold: t.escalationRecall, pass: escalationRecall >= t.escalationRecall },
    groundednessAccuracy: {
      value: draftResults.length ? draftResults.filter((r) => r.pass).length / draftResults.length : 1,
      threshold: t.groundednessAccuracy,
      pass: (draftResults.length ? draftResults.filter((r) => r.pass).length / draftResults.length : 1) >= t.groundednessAccuracy,
    },
    safetyNoFabrication: { value: noFabrication, threshold: t.safetyNoFabrication, pass: noFabrication >= t.safetyNoFabrication },
    reviewCorrectness: { value: reviewCorrectness, threshold: t.reviewCorrectness, pass: reviewCorrectness >= t.reviewCorrectness },
  };
  report.thresholdChecks = checks;
  const allPass = Object.values(checks).every((c) => c.pass);
  report.passed = allPass;

  const llmModel = useLlm ? loadConfig().llmModel : null;
  const pricing = loadPricing();
  const { costUsd, basis } = priceCost(pricing, llmModel, usageTotals.input_tokens, usageTotals.output_tokens);
  report.cost = {
    model: llmModel,
    input_tokens: usageTotals.input_tokens,
    output_tokens: usageTotals.output_tokens,
    cost_usd: costUsd,
    cost_basis: basis,
    pricing_table: 'shared-docs/evals/pricing.json',
    pricing_source: pricing?.source ?? null,
    pricing_retrieved_at: pricing?.retrieved_at ?? null,
  };

  const slug = useLlm ? 'llm' : 'rules';
  writeFileSync(resolve(__dirname, 'report.json'), JSON.stringify(report, null, 2));
  writeFileSync(resolve(__dirname, `report-${slug}.json`), JSON.stringify(report, null, 2));

  if (jsonOnly) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    console.log(`Task 2 evals — classifier=${classifier.name}`);
    console.log(`cost: model=${llmModel ?? 'n/a'} input_tokens=${usageTotals.input_tokens} output_tokens=${usageTotals.output_tokens} cost_usd=${costUsd}`);
    console.log(`classification: ${JSON.stringify(report.classification)}`);
    console.log(`drafts: ${report.drafts && (report.drafts as { passed: number }).passed}/${(report.drafts as { cases: number }).cases} passed`);
    console.log(`safety:  ${(report.safety as { passed: number }).passed}/${(report.safety as { cases: number }).cases} passed`);
    console.log(`review:  ${(report.review as { passed: number }).passed}/${(report.review as { cases: number }).cases} passed`);
    console.log('threshold checks:');
    for (const [k, v] of Object.entries(checks)) {
      console.log(`  ${v.pass ? 'PASS' : 'FAIL'} ${k}: ${v.value.toFixed(3)} (>= ${v.threshold})`);
    }
    console.log(`RESULT: ${allPass ? 'ALL THRESHOLDS MET' : 'THRESHOLD FAILURES'}`);
    console.log('report written to evals/report.json');
  }

  process.exit(allPass ? 0 : 1);
}

function round(n: number): number {
  return Math.round(n * 1000) / 1000;
}

main().catch((err) => {
  console.error('eval run failed:', err);
  process.exit(2);
});
