import pytest

from evals.run_evals import (
    DEFAULT_CASES,
    cost_block,
    load_pricing,
    select_split,
)
import json


def load_all_cases():
    data = json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))
    return data["cases"]


class RulesExtractor:
    pass


class FakeUsageProvider:
    model_name = "anthropic/claude-sonnet-4.6"
    usage_totals = {"input_tokens": 2_000_000, "output_tokens": 100_000}
    provider_reported_cost_usd = None


class FakeUsageExtractor:
    provider = FakeUsageProvider()


def test_pricing_table_covers_compared_models_with_source_and_date():
    pricing = load_pricing()
    assert pricing["source"].startswith("OpenRouter")
    assert pricing["retrieved_at"]
    for model in ("anthropic/claude-haiku-4.5", "anthropic/claude-sonnet-4.6"):
        entry = pricing["models"][model]
        assert entry["input"] > 0
        assert entry["output"] > 0


def test_cost_block_prices_tokens_from_shared_table():
    block = cost_block(FakeUsageExtractor(), load_pricing())
    # 2.0 MTok x $3.00/MTok + 0.1 MTok x $15.00/MTok
    assert block["cost_usd"] == pytest.approx(7.5)
    assert block["model"] == "anthropic/claude-sonnet-4.6"
    assert block["pricing_table"] == "shared-docs/evals/pricing.json"
    assert block["pricing_retrieved_at"] == load_pricing()["retrieved_at"]


def test_cost_block_rules_extractor_costs_zero():
    block = cost_block(RulesExtractor(), load_pricing())
    assert block["model"] is None
    assert block["input_tokens"] == 0
    assert block["cost_usd"] == 0.0
    assert "no chat tokens" in block["cost_basis"]


def test_every_case_declares_a_split():
    cases = load_all_cases()
    assert len(cases) == 20
    assert all(case.get("split") in {"tuning", "holdout"} for case in cases)


def test_split_selection_counts():
    cases = load_all_cases()
    tuning = select_split(cases, "tuning")
    holdout = select_split(cases, "holdout")
    assert len(tuning) == 14
    assert len(holdout) == 6
    assert len(select_split(cases, "all")) == 20
    assert {c["id"] for c in tuning}.isdisjoint({c["id"] for c in holdout})


def test_select_split_rejects_empty_selection():
    with pytest.raises(SystemExit):
        select_split([{"id": "a"}], "holdout")
