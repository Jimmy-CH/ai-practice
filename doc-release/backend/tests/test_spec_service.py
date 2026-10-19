import json

import pytest

from app.services import git_service, llm_service, spec_service
from app.services.errors import RunCancelled
from tests.gitfix import commit, init_repo, tag, write_files


def test_list_tree_reads_ref_without_checkout(tmp_path):
    repo = init_repo(tmp_path)
    write_files(repo, {"src/a.ts": "export const A = 1;\n", "docs/readme.md": "# x\n"})
    commit(repo, "init")
    tag(repo, "v1.0.0")
    paths = git_service.list_tree(str(repo), "v1.0.0")
    assert "src/a.ts" in paths and "docs/readme.md" in paths


def test_module_key_strips_container_dirs():
    assert spec_service.module_key("backend/app/services/pipeline.py") == "app/services"
    assert spec_service.module_key("frontend/src/views/Console.vue") == "src/views"
    assert spec_service.module_key("src/report/export/stream.ts") == "report/export"
    assert spec_service.module_key("api/order/list.go") == "api/order"
    assert spec_service.module_key("src/a.ts") == "src"
    assert spec_service.module_key("README.md") == "根目录"


def test_snapshot_filter_skips_deps_secrets_and_binaries():
    for bad in ["node_modules/x.js", ".env", "a/.env.local", "keys/server.pem",
                "credentials.json", "logo.png", "package-lock.json", "dist/app.js", "venv/x.py"]:
        assert not spec_service.is_candidate_file(bad)
    for good in ["src/a.ts", "app/main.py", "README.md", "api/order/list.go"]:
        assert spec_service.is_candidate_file(good)


def test_group_files_caps_modules_and_marks_changed():
    paths = [f"m{i}/a.py" for i in range(15)] + ["m0/b.py"]
    groups = spec_service.build_module_groups(paths, changed_paths={"m0/a.py"})
    selected, skipped = spec_service.select_modules(groups, max_modules=12)
    assert skipped == 3
    assert selected[0]["name"] == "m0" and selected[0]["changed"] is True


def test_normalize_module_payload_defaults_and_filters():
    raw = {"responsibility": "负责订单",
           "functions": [{"name": "下单", "logic": "创建订单",
                          "roles": ["用户"], "priority": "P9"}],
           "flows": [{"title": "下单", "mermaid": "```mermaid\nflowchart TD\n A-->B\n```"},
                     {"title": "坏图", "mermaid": "not a diagram"}],
           "entities": [{"name": "Order", "fields": [{"name": "id", "type": "String(36)"}],
                         "relations": [{"target": "User", "cardinality": "??"}]}]}
    out = spec_service.normalize_module_payload(raw)
    assert out["functions"][0]["priority"] == "P1"
    assert out["flows"][0]["mermaid"].startswith("flowchart TD")
    assert len(out["flows"]) == 1
    assert out["entities"][0]["relations"][0]["cardinality"] == "||--o{"
    assert out["rules"] == [] and out["errorCodes"] == []
    assert set(out["nfr"]) == set(spec_service.NFR_KEYS)


async def test_generate_spec_degrades_module_on_llm_error(tmp_path, monkeypatch):
    repo = init_repo(tmp_path)
    write_files(repo, {"src/a.ts": "export const A = 1;\n"})
    commit(repo, "init")

    async def bad(system, user):
        raise RuntimeError("网关不可达")

    monkeypatch.setattr(llm_service, "_chat", bad)
    spec = await spec_service.generate_product_spec(
        str(repo), "HEAD", "demo", {"files": [], "modules": []})
    assert spec["modules"][0]["degraded"] is True
    assert spec["degradedModules"]
    assert spec["overview"]["name"] == "demo"
    assert len(spec["lowConfidence"]) == 2


async def test_generate_spec_overview_falls_back(tmp_path, monkeypatch):
    repo = init_repo(tmp_path)
    write_files(repo, {"src/a.ts": "export const A = 1;\n"})
    commit(repo, "init")

    async def mixed(system, user):
        if "全局架构分析师" in system:
            raise RuntimeError("概览超时")
        return json.dumps({
            "responsibility": "示例模块",
            "functions": [{"name": "示例功能", "logic": "读 A", "roles": ["研发"],
                          "priority": "P0"}],
            "flows": [], "entities": [], "enums": [], "rules": [], "errorCodes": [],
            "nfr": {},
        }, ensure_ascii=False)

    monkeypatch.setattr(llm_service, "_chat", mixed)
    spec = await spec_service.generate_product_spec(
        str(repo), "HEAD", "demo", {"files": [], "modules": []})
    assert spec["modules"][0]["degraded"] is False
    assert spec["overview"]["name"] == "demo"
    assert any("全局概览" in item for item in spec["lowConfidence"])
    assert spec["roles"][0]["role"] == "研发"


async def test_generate_spec_cancel_raises(tmp_path):
    with pytest.raises(RunCancelled):
        await spec_service.generate_product_spec(
            str(tmp_path), "HEAD", "demo", {"files": [], "modules": []},
            cancel_check=lambda: True)
