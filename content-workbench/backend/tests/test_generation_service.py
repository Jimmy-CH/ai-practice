import json

import pytest

from app.services.generation import FakeGenerator, GenerationValidationError, validate_generation

ALLOWED = {"s1": "智能报表支持拖拽分析。", "s2": "支持导出 Excel。"}


def test_validate_accepts_complete_output():
    items = FakeGenerator.build(["s1", "s2"], theme="智能报表", audience="分析师")
    results = validate_generation(items, ALLOWED)
    assert {kind for kind, _, _ in results} == {"announcement", "faq", "poster"}
    assert results[0][2][0]["text"] == "智能报表支持拖拽分析。"


def test_validate_rejects_unknown_source():
    items = FakeGenerator.build(["sX"], theme="t", audience="a")
    with pytest.raises(GenerationValidationError):
        validate_generation(items, ALLOWED)


def test_validate_rejects_missing_field():
    items = FakeGenerator.build(["s1"], theme="t", audience="a")
    items[0]["content"].pop("title")
    with pytest.raises(GenerationValidationError):
        validate_generation(items, ALLOWED)


def test_validate_rejects_incomplete_kinds():
    items = [item for item in FakeGenerator.build(["s1"], theme="t", audience="a") if item["kind"] != "poster"]
    with pytest.raises(GenerationValidationError):
        validate_generation(items, ALLOWED)


def test_validate_rejects_empty_faq_item_citations():
    items = FakeGenerator.build(["s1"], theme="t", audience="a")
    items[1]["content"]["items"][0]["source_ids"] = []
    with pytest.raises(GenerationValidationError):
        validate_generation(items, ALLOWED)


def test_fake_parses_assets_wrapper():
    payload = json.dumps({"assets": FakeGenerator.build(["s1"], theme="t", audience="a")}, ensure_ascii=False)
    items = json.loads(payload)["assets"]
    assert len(items) == 3
