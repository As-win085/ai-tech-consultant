import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export interface PricingEntry {
  label?: string;
  input: number;
  output: number;
}

export interface PricingTable {
  source: string;
  source_url: string;
  retrieved_at: string;
  currency: string;
  unit: string;
  models: Record<string, PricingEntry>;
}

export const PRICING_TABLE_PATH = resolve(__dirname, '..', '..', 'shared-docs', 'evals', 'pricing.json');

export function loadPricing(): PricingTable | null {
  try {
    return JSON.parse(readFileSync(PRICING_TABLE_PATH, 'utf8')) as PricingTable;
  } catch {
    return null;
  }
}

export interface CostResult {
  costUsd: number | null;
  basis: string;
}

/** Price token usage from the shared pricing table (constant, with source and date). */
export function priceCost(
  pricing: PricingTable | null,
  modelId: string | null,
  inputTokens: number,
  outputTokens: number,
): CostResult {
  const entry = modelId ? pricing?.models?.[modelId] : undefined;
  if (pricing && entry) {
    const cost = (inputTokens / 1_000_000) * entry.input + (outputTokens / 1_000_000) * entry.output;
    return {
      costUsd: Math.round(cost * 1e6) / 1e6,
      basis: `tokens x shared-docs/evals/pricing.json list prices (source: ${pricing.source}, retrieved: ${pricing.retrieved_at})`,
    };
  }
  if (inputTokens === 0 && outputTokens === 0) {
    return { costUsd: 0, basis: 'no chat tokens used (offline provider or run failed before chat)' };
  }
  return { costUsd: null, basis: 'model is missing from the pricing table; cost unavailable' };
}
