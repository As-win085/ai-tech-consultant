import pytest

from evals.run_evals import (
    DEFAULT_CASES,
    cost_block,
    load_cases,
    load_pricing,
    select_split,
)


class FakeUsageChat:
    model_name = "anthropic/claude-haiku-4.5"
    usage_totals = {"input_tokens": 1_000_000, "output_tokens": 200_000}
    provider_reported_cost_usd = None


def test_pricing_table_covers_compared_models_with_source_and_date():
    pricing = load_pricing()
    assert pricing["source"].startswith("OpenRouter")
    assert pricing["source_url"].startswith("https://")
    assert pricing["retrieved_at"]
    for model in ("anthropic/claude-haiku-4.5", "anthropic/claude-sonnet-4.6"):
        entry = pricing["models"][model]
        assert entry["input"] > 0
        assert entry["output"] > 0
        assert entry["label"] in {"cheap", "strong"}


def test_cost_block_prices_tokens_from_shared_table():
    pricing = load_pricing()
    block = cost_block(FakeUsageChat(), pricing)
    # 1.0 MTok x $1.00/MTok + 0.2 MTok x $5.00/MTok
    assert block["cost_usd"] == pytest.approx(2.0)
    assert block["input_tokens"] == 1_000_000
    assert block["output_tokens"] == 200_000
    assert block["pricing_table"] == "shared-docs/evals/pricing.json"
    assert block["pricing_source"] == pricing["source"]
    assert block["pricing_retrieved_at"] == pricing["retrieved_at"]
    assert block["embedding_cost_included"] is False


def test_cost_block_offline_provider_costs_zero():
    class OfflineChat:
        model_name = "fake-chat"
        usage_totals = {"input_tokens": 0, "output_tokens": 0}

    block = cost_block(OfflineChat(), load_pricing())
    assert block["cost_usd"] == 0.0
    assert "no chat tokens" in block["cost_basis"]


def test_cost_block_unknown_model_with_tokens_is_unavailable():
    class MysteryChat:
        model_name = "mystery-model"
        usage_totals = {"input_tokens": 10, "output_tokens": 5}

    block = cost_block(MysteryChat(), load_pricing())
    assert block["cost_usd"] is None
    assert "missing from the pricing table" in block["cost_basis"]


def test_cost_block_without_pricing_table_is_unavailable():
    class Chat:
        model_name = "anthropic/claude-haiku-4.5"
        usage_totals = {"input_tokens": 100, "output_tokens": 10}

    block = cost_block(Chat(), {})
    assert block["cost_usd"] is None


def test_every_case_declares_a_split():
    cases = load_cases(DEFAULT_CASES)
    assert len(cases) == 29
    assert all(case.get("split") in {"tuning", "holdout"} for case in cases)


def test_split_selection_counts():
    cases = load_cases(DEFAULT_CASES)
    tuning = select_split(cases, "tuning")
    holdout = select_split(cases, "holdout")
    assert len(tuning) == 20
    assert len(holdout) == 9
    assert len(select_split(cases, "all")) == 29
    assert {c["id"] for c in tuning}.isdisjoint({c["id"] for c in holdout})


def test_cases_without_split_field_count_as_tuning():
    cases = [{"id": "a", "category": "answerable"}, {"id": "b", "split": "holdout"}]
    assert [c["id"] for c in select_split(cases, "tuning")] == ["a"]
    assert [c["id"] for c in select_split(cases, "holdout")] == ["b"]


def test_select_split_rejects_empty_selection():
    with pytest.raises(SystemExit):
        select_split([{"id": "a"}], "holdout")
