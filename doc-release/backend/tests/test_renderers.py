import json

from app.services import renderers as r

RESULT = {
    "features": [
        {"tag": "缺陷修复", "risk": "中", "breaking": False, "title": "报表导出超时修复",
         "biz": "导出口径改为分片流式写出，超时问题解决", "tech": "新增 streamWrite 分片写入",
         "visible": "导出不再超时", "scope": "报表导出", "acceptance": "1 万行导出 30 秒内完成",
         "action": "无需操作", "role": "研发", "paths": ["src/report/export/stream.ts"]},
        {"tag": "破坏性变更", "risk": "高", "breaking": True, "title": "v1 下单接口下线",
         "biz": "老接口不再受理流量", "tech": "CreateOrderV1 删除，返回 410",
         "visible": "老客户端调用失败", "scope": "对外 API", "acceptance": "监控无 /v1 流量",
         "action": "确认存量客户端已迁移", "role": "产品", "paths": ["api/legacy/order.go"]},
    ],
    "highlights": ["导出稳定性提升"],
    "lowConfidence": [],
    "contractSignals": [{"kind": "route_removed", "path": "api/legacy/order.go",
                         "message": "接口路径 /v1/order/create 已移除或变更"}],
    "llm": {"provider": "xingyu", "model": "xingyu:ROBOT_00000149", "prompt": "docrelease/v1",
            "confidence": 0.9, "inputChars": 1200, "outputChars": 800, "glossaryHits": 2,
            "lowConfidence": []},
    "meta": {"runId": "run-123", "repoName": "order-center", "version": "v2.13.4",
             "branch": "main", "headShort": "abc1234", "range": "v2.13.3..v2.13.4",
             "trigger": "手动触发", "generatedAt": "2026-10-14 12:00:00",
             "stats": {"commits": 3, "files": 4, "modules": 1, "added": 51, "removed": 16, "days": 2},
             "modules": ["src/report"], "pipeline": [{"name": "定位仓库与变更范围", "ok": True, "ms": 120}]},
}


def test_checklist_has_bom_header_and_rows():
    text = r.render_checklist(RESULT, {"tone": "business", "mask": False})
    assert text.startswith("\ufeff")
    lines = text.strip().splitlines()
    assert lines[0].lstrip("\ufeff").startswith("序号,版本,标签")
    assert "报表导出超时修复" in lines[1]
    assert len(lines) == 3


def test_checklist_tone_switches_explanation():
    biz = r.render_checklist(RESULT, {"tone": "business"})
    tech = r.render_checklist(RESULT, {"tone": "tech"})
    assert "分片流式写出，超时问题解决" in biz
    assert "新增 streamWrite" in tech


def test_checklist_mask_hides_paths():
    text = r.render_checklist(RESULT, {"tone": "business", "mask": True})
    assert "src/report/export/stream.ts" not in text
    assert "…/export/stream.ts" in text


def test_checklist_quotes_commas():
    result = json.loads(json.dumps(RESULT))
    result["features"][0]["title"] = "标题,带逗号"
    text = r.render_checklist(result, {})
    assert '"标题,带逗号"' in text


def test_document_sections():
    text = r.render_document(RESULT, {"tone": "business", "mask": False})
    for section in ["版本概览", "发布亮点", "功能清单", "破坏性变更", "涉及模块与文件",
                    "验收清单", "上线操作步骤", "溯源说明"]:
        assert section in text
    assert "确认存量客户端已迁移" in text


def test_trace_structure_and_sizes():
    text = r.render_trace(RESULT, {"tone": "business", "mask": False},
                          sizes={"checklist": 1000, "document": 2000, "trace": 3000})
    data = json.loads(text)
    assert data["runId"] == "run-123"
    assert data["generator"] == "释文 DocRelease"
    assert data["trigger"]["mode"] == "manual"
    assert data["range"]["base"] == "v2.13.3" and data["range"]["commit"] == "abc1234"
    assert data["confidence"] == 0.9
    assert {a["kind"]: a["bytes"] for a in data["artifacts"]} == {
        "checklist": 1000, "document": 2000, "trace": 3000}
    assert any(s["kind"] == "route_removed" for s in data["contractSignals"])


def test_trace_mask_masks_commit_and_paths():
    data = json.loads(r.render_trace(RESULT, {"tone": "business", "mask": True}))
    assert data["range"]["commit"] == "abc****"
    assert data["features"][0]["paths"] == ["…/export/stream.ts"]


def test_trace_mask_hides_signal_paths():
    data = json.loads(r.render_trace(RESULT, {"tone": "business", "mask": True}))
    assert data["contractSignals"][0]["path"] == "…/legacy/order.go"
    assert data["contractSignals"][0]["message"].startswith("接口路径")
    open_data = json.loads(r.render_trace(RESULT, {"tone": "business", "mask": False}))
    assert open_data["contractSignals"][0]["path"] == "api/legacy/order.go"
