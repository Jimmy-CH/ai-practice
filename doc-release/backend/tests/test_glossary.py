from app.prompts.docrelease_v1 import PROMPT_VERSION, SYSTEM_PROMPT_TEMPLATE, build_user_prompt
from app.services import glossary as g


def test_glossary_loads_and_has_terms():
    data = g.load_glossary()
    assert data["version"]
    assert len(data["terms"]) >= 20


def test_match_terms_by_term_and_alias():
    hits = g.match_terms("导出改为分片流式写出，并加了 withRetry 指数退避")
    assert "分片流式写出" in hits and "指数退避" in hits


def test_match_terms_empty():
    assert g.match_terms("nothing here") == []


def test_prompt_section_contains_terms():
    section = g.build_glossary_prompt_section()
    assert "券叠加" in section and "事件溯源" in section


def test_system_prompt_renders_glossary():
    text = SYSTEM_PROMPT_TEMPLATE.format(glossary="术语占位")
    assert "术语占位" in text
    assert "features" in text
    assert PROMPT_VERSION == "docrelease/v1"


def test_build_user_prompt_includes_symbols_and_signals():
    chunk = {"name": "src/report", "files": [{
        "path": "src/report/export/index.ts", "status": "m", "added": 5, "removed": 2,
        "symbols_summary": "新增 1、删除 0、修改 0",
        "contract_signals": [{"message": "常量 X 由 1 变为 2"}],
        "lines": [{"t": "add", "s": "const a = 1;"}], "truncated": False}]}
    prompt = build_user_prompt(chunk)
    assert "src/report/export/index.ts" in prompt
    assert "符号变更：新增 1、删除 0、修改 0" in prompt
    assert "契约信号：常量 X 由 1 变为 2" in prompt
    assert "+const a = 1;" in prompt
