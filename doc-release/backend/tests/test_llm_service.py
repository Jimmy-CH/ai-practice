import json

import pytest

from app.services import llm_service


def _file(path, lines=3, status="m"):
    return {"path": path, "status": status, "added": 1, "removed": 1, "binary": False,
            "truncated": False,
            "lines": [{"t": "add", "s": f"const x{i} = {i};"} for i in range(lines)]}


def _changeset(files, modules=None, signals=None):
    return {"files": files, "stats": {}, "commits": [], "contract_signals": signals or [],
            "modules": modules or [{"name": "src", "files": [f["path"] for f in files]}]}


def test_extract_json_plain():
    assert llm_service.extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced_with_noise():
    text = '好的，结果如下：\n```json\n{"a": {"b": "}"}}\n```\n以上。'
    assert llm_service.extract_json(text) == {"a": {"b": "}"}}


def test_extract_json_raises_without_object():
    with pytest.raises(ValueError):
        llm_service.extract_json("没有 JSON")


def test_build_chunks_splits_by_module_and_limit():
    files = [_file(f"src/a/f{i}.ts") for i in range(10)] + [_file("src/b/g.ts")]
    cs = _changeset(files, modules=[
        {"name": "src/a", "files": [f["path"] for f in files[:10]]},
        {"name": "src/b", "files": ["src/b/g.ts"]},
    ])
    chunks = llm_service.build_chunks(cs, max_files=8)
    assert [c["name"] for c in chunks] == ["src/a·1", "src/a·2", "src/b"]


async def test_rewrite_success(monkeypatch):
    async def fake_chat(system, user):
        return json.dumps({
            "features": [{"title": "报表导出支持分片流式写出", "biz": "分片流式写出避免超时",
                          "tech": "新增 streamWrite", "tag": "新增功能",
                          "paths": ["src/report/export/stream.ts"]}],
            "highlights": ["导出稳定性提升"], "confidence": 0.92}, ensure_ascii=False)

    monkeypatch.setattr(llm_service, "_chat", fake_chat)
    cs = _changeset([_file("src/report/export/stream.ts")],
                    modules=[{"name": "src/report", "files": ["src/report/export/stream.ts"]}])
    out = await llm_service.rewrite_changes(cs)
    assert out["ok"] and not out["all_failed"]
    assert out["features"][0]["title"] == "报表导出支持分片流式写出"
    assert out["features"][0]["role"] == "研发"          # 默认字段补齐
    assert out["llm"]["confidence"] == 0.92
    assert out["llm"]["glossaryHits"] >= 1               # 命中「分片流式写出」
    assert "导出稳定性提升" in out["highlights"]


async def test_rewrite_degraded_when_all_fail(monkeypatch):
    async def bad_chat(system, user):
        raise RuntimeError("网关不可达")

    monkeypatch.setattr(llm_service, "_chat", bad_chat)
    out = await llm_service.rewrite_changes(_changeset([_file("src/a/x.ts")]))
    assert out["all_failed"] is True and out["ok"] is False
    assert out["features"][0]["title"].endswith("变更待人工确认")
    assert out["lowConfidence"]


async def test_rewrite_partial_failure_keeps_success(monkeypatch):
    async def sometimes(system, user):
        if "src/a/x.ts" in user:
            raise RuntimeError("超时")
        return json.dumps({"features": [{"title": "另一个模块的功能点", "biz": "b", "tech": "t"}],
                           "highlights": [], "confidence": 0.8}, ensure_ascii=False)

    monkeypatch.setattr(llm_service, "_chat", sometimes)
    cs = _changeset([_file("src/a/x.ts"), _file("src/b/y.ts")], modules=[
        {"name": "src/a", "files": ["src/a/x.ts"]},
        {"name": "src/b", "files": ["src/b/y.ts"]},
    ])
    out = await llm_service.rewrite_changes(cs)
    assert out["ok"] is True and out["all_failed"] is False
    assert any("src/a" in msg for msg in out["lowConfidence"])
    assert any(f["title"] == "另一个模块的功能点" for f in out["features"])


def test_validate_payload_accepts_valid():
    llm_service.validate_payload({"features": [{"title": "T"}], "highlights": []})
    llm_service.validate_payload({"features": [], "confidence": 0.5})


def test_validate_payload_rejects_bad_shapes():
    for bad in ([], {"features": {}}, {"features": ["x"]},
                {"features": [{"title": ""}]},
                {"features": [], "highlights": "x"}):
        with pytest.raises(ValueError):
            llm_service.validate_payload(bad)


async def test_rewrite_degrades_on_invalid_shape(monkeypatch):
    async def bad_shape(system, user):
        return json.dumps({"features": {"title": "不是数组"}})

    monkeypatch.setattr(llm_service, "_chat", bad_shape)
    out = await llm_service.rewrite_changes(_changeset([_file("src/a/x.ts")]))
    assert out["all_failed"] is True
    assert out["features"][0]["title"].endswith("变更待人工确认")


async def test_contract_signals_enter_highlights(monkeypatch):
    async def fake_chat(system, user):
        return json.dumps({"features": [{"title": "T", "biz": "b", "tech": "t"}],
                           "highlights": [], "confidence": 1.0}, ensure_ascii=False)

    monkeypatch.setattr(llm_service, "_chat", fake_chat)
    cs = _changeset([_file("src/pay/verify.ts")],
                    signals=[{"kind": "symbol_removed", "path": "src/pay/verify.ts",
                              "message": "导出符号 verifyCallback 已删除"}])
    out = await llm_service.rewrite_changes(cs)
    assert any("导出符号 verifyCallback 已删除" in h for h in out["highlights"])
