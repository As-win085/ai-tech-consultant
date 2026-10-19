import { loadPricing, priceCost, PRICING_TABLE_PATH } from '../evals/pricing';

describe('shared eval pricing', () => {
  it('loads the committed pricing table with source and retrieval date', () => {
    const pricing = loadPricing();
    expect(pricing).not.toBeNull();
    expect(pricing!.source).toContain('OpenRouter');
    expect(pricing!.source_url).toMatch(/^https:\/\//);
    expect(pricing!.retrieved_at).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(PRICING_TABLE_PATH).toContain('shared-docs');
    expect(pricing!.models['anthropic/claude-haiku-4.5']).toBeDefined();
    expect(pricing!.models['anthropic/claude-sonnet-4.6']).toBeDefined();
  });

  it('prices tokens from the table (1 MTok in + 0.2 MTok out on haiku-4.5)', () => {
    const pricing = loadPricing();
    const { costUsd, basis } = priceCost(pricing, 'anthropic/claude-haiku-4.5', 1_000_000, 200_000);
    expect(costUsd).toBeCloseTo(2.0, 6);
    expect(basis).toContain('pricing.json list prices');
    expect(basis).toContain('retrieved');
  });

  it('returns zero cost with a clear basis when no tokens were used', () => {
    const { costUsd, basis } = priceCost(loadPricing(), null, 0, 0);
    expect(costUsd).toBe(0);
    expect(basis).toContain('no chat tokens used');
  });

  it('returns unavailable cost for a model missing from the table', () => {
    const { costUsd, basis } = priceCost(loadPricing(), 'mystery-model', 100, 50);
    expect(costUsd).toBeNull();
    expect(basis).toContain('missing from the pricing table');
  });

  it('returns unavailable cost when the pricing table cannot be read', () => {
    const { costUsd, basis } = priceCost(null, 'anthropic/claude-haiku-4.5', 100, 50);
    expect(costUsd).toBeNull();
    expect(basis).toContain('missing from the pricing table');
  });
});
