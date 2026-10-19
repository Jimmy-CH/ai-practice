# doc-release 九节产品说明书 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `product-doc.md` 从八节发布说明升级为基于 head_ref 全量快照生成的九节产品说明书，并在前端渲染 mermaid 流程图/ER 图。

**Architecture:** 保持五步流水线；步骤 3 并发执行「diff 功能点改写」与「全量快照产品说明书生成」；分模块 LLM 输出结构化 JSON，`spec_renderer` 确定性渲染九节 Markdown；历史运行无 `spec` 时回退旧八节。

**Tech Stack:** Python 3.11 / FastAPI / asyncio / tree-sitter（现有）/ marked + mermaid 11 / Vue 3 + Element Plus。

---

## 文件结构

| 文件 | 责任 |
|---|---|
| `doc-release/backend/app/services/git_service.py` | 新增 `list_tree`（`git ls-tree -r --name-only -z`） |
| `doc-release/backend/app/prompts/spec_v1.py`（新） | 模块画像与全局概览提示词、`PROMPT_VERSION="spec/v1"` |
| `doc-release/backend/app/services/spec_service.py`（新） | 快照过滤/聚类、分模块 LLM、概览、降级、指标 |
| `doc-release/backend/app/services/spec_renderer.py`（新） | 九节 Markdown 确定性渲染、ER 汇总、mask |
| `doc-release/backend/app/services/renderers.py` | `render_document` 分发（spec → 九节，否则旧八节） |
| `doc-release/backend/app/services/pipeline_service.py` | 步骤 3 并发、步骤名、日志、result.spec |
| `doc-release/backend/app/config.py` | `spec_max_modules/spec_max_files_per_module/spec_max_file_chars/spec_concurrency` |
| `doc-release/backend/tests/conftest.py` | LLM 打桩按提示词标记分流 |
| `doc-release/backend/tests/test_spec_service.py`（新） | 快照/校验/降级/取消测试 |
| `doc-release/backend/tests/test_renderers.py` | 九节、mermaid、mask、旧运行回退 |
| `doc-release/backend/tests/test_pipeline.py` | result.spec、九节产物、仍 5 步 3 产物 |
| `doc-release/backend/tests/test_api_runs.py` | document 断言改九节、慢速打桩分流 |
| `doc-release/backend/e2e_smoke.py` | 打桩分流、九节/mermaid 断言 |
| `doc-release/frontend/package.json` | 新增 `mermaid` |
| `doc-release/frontend/src/render/artifacts.ts` | mermaid 代码块 → `<div class="mermaid">` |
| `doc-release/frontend/src/components/OutputPanel.vue` | mermaid 动态渲染 + 单图失败降级 |
| `doc-release/frontend/src/data/steps.ts` | 步骤 4 名称更新 |
| `doc-release/docs/产品说明.md` | 同步九节生成、mermaid、步骤名、限额说明 |

---

### Task 1: git 快照枚举与模块聚类

**Files:**
- Modify: `backend/app/services/git_service.py`
- Create: `backend/app/services/spec_service.py`
- Test: `backend/tests/test_spec_service.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path
from app.services import git_service
from app.services import spec_service
from tests.gitfix import commit, init_repo, write_files


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
    assert spec_service.module_key("README.md") == "根目录"


def test_snapshot_filter_skips_deps_secrets_and_binaries():
    for bad in ["node_modules/x.js", ".env", "a/.env.local", "keys/server.pem",
                "logo.png", "package-lock.json", "dist/app.js", "venv/x.py"]:
        assert not spec_service.is_candidate_file(bad)
    for good in ["src/a.ts", "app/main.py", "README.md", "api/order/list.go"]:
        assert spec_service.is_candidate_file(good)


def test_group_files_caps_modules_and_marks_changed():
    paths = [f"m{i}/a.py" for i in range(15)] + ["m0/b.py"]
    groups = spec_service.build_module_groups(paths, changed_paths={"m0/a.py"})
    selected, skipped = spec_service.select_modules(groups, max_modules=12)
    assert skipped == 3
    assert selected[0]["name"] == "m0" and selected[0]["changed"] is True
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .\venv\Scripts\python.exe -m pytest tests/test_spec_service.py -q`
Expected: collection error（`list_tree` / `spec_service` 不存在）

- [ ] **Step 3: 实现**

`git_service.py` 追加：

```python
def list_tree(repo_path: str, ref: str) -> list[str]:
    """枚举指定引用下的全部文件路径（只读，-z 防特殊字符转义）。"""
    out = _run_git(repo_path, ["ls-tree", "-r", "--name-only", "-z", _check_ref(ref)])
    return [p for p in out.split("\x00") if p]
```

`spec_service.py` 先落纯函数与常量：

```python
_SKIP_DIRS = {".git", "node_modules", "dist", "build", "out", "venv", ".venv",
              "__pycache__", ".pytest_cache", ".mypy_cache", ".idea", ".vscode",
              "archive", "static", "coverage", ".next", ".nuxt", "target", "bin", "obj"}
_SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".pdf",
                  ".zip", ".gz", ".tar", ".whl", ".exe", ".dll", ".so", ".dylib",
                  ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".lock"}
_SKIP_NAMES = {".env", ".npmrc", ".netrc", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
_TEXT_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".go", ".java", ".kt",
              ".rs", ".cs", ".rb", ".php", ".sql", ".md", ".json", ".yaml", ".yml",
              ".toml", ".ini", ".cfg", ".sh", ".ps1", ".gradle", ".xml", ".proto"}
_CONTAINER_DIRS = {"backend", "frontend", "server", "client", "web", "src", "app",
                   "packages", "apps"}


def is_candidate_file(path: str) -> bool:
    parts = Path(path).parts
    if any(p in _SKIP_DIRS for p in parts):
        return False
    name = parts[-1]
    if name in _SKIP_NAMES or name.startswith(".env"):
        return False
    if name.startswith(".") or name.endswith(".min.js"):
        return False
    if name.endswith(".pem") or name.endswith(".key") or name.startswith("id_rsa"):
        return False
    if Path(name).suffix.lower() not in _TEXT_EXTS:
        return False
    return True


def module_key(path: str) -> str:
    dirs = list(Path(path).parts[:-1])
    if dirs and dirs[0] in _CONTAINER_DIRS:
        dirs = dirs[1:]
    if not dirs:
        return "根目录"
    return "/".join(dirs[:2])


def build_module_groups(paths: list[str], changed_paths: set[str]) -> list[dict]:
    groups: dict[str, dict] = {}
    for path in paths:
        if not is_candidate_file(path):
            continue
        key = module_key(path)
        g = groups.setdefault(key, {"name": key, "files": [], "changed": False})
        g["files"].append(path)
        if path in changed_paths:
            g["changed"] = True
    return sorted(groups.values(), key=lambda g: g["name"])


def select_modules(groups: list[dict], max_modules: int) -> tuple[list[dict], int]:
    ordered = sorted(groups, key=lambda g: (g["changed"], len(g["files"])), reverse=True)
    return ordered[:max_modules], max(0, len(ordered) - max_modules)
```

- [ ] **Step 4: 跑测试**

Run: `cd backend && .\venv\Scripts\python.exe -m pytest tests/test_spec_service.py -q`
Expected: 4 passed

---

### Task 2: 提示词、校验与降级

**Files:**
- Create: `backend/app/prompts/spec_v1.py`
- Modify: `backend/app/services/spec_service.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_spec_service.py`

- [ ] **Step 1: 加失败测试**

```python
from app.prompts import spec_v1
from app.services import llm_service, spec_service


def test_normalize_module_payload_defaults_and_filters():
    raw = {"responsibility": "负责订单", "functions": [{"name": "下单", "logic": "创建订单",
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


async def test_generate_spec_cancel_raises(tmp_path):
    repo = init_repo(tmp_path)
    write_files(repo, {"src/a.ts": "export const A = 1;\n"})
    commit(repo, "init")
    with pytest.raises(RunCancelled):
        await spec_service.generate_product_spec(
            str(repo), "HEAD", "demo", {"files": [], "modules": []},
            cancel_check=lambda: True)
```

- [ ] **Step 2: 实现 `spec_v1.py`**

要点：
- `PROMPT_VERSION = "spec/v1"`。
- 两套系统提示词，均含标记 `产品说明书生成引擎（spec/v1）`，便于测试打桩分流。
- 模块用户提示词以 `模块：` 开头；概览以 `项目：` 开头。
- JSON 契约与设计文档一致；要求「无证据的数组留空、mermaid 首行白名单、只输出 JSON」。

- [ ] **Step 3: 实现 `spec_service` 编排**

```python
def normalize_module_payload(raw: dict) -> dict          # 默认值/枚举/清洗
def normalize_overview_payload(raw: dict) -> dict
def _clean_mermaid(text: str, allow: tuple[str, ...]) -> str
def _fallback_module(group: dict, reason: str) -> dict
def _fallback_overview(repo_name: str, modules: list[dict]) -> dict
async def generate_product_spec(repo_path, ref, repo_name, changeset,
                                cancel_check=None, log=None) -> dict
```

- 快照：`list_tree` → 过滤 → `build_module_groups` → `select_modules(settings.spec_max_modules)` → `read_files` 批量读。
- 单模块：`llm_service._chat(system, user)` × 重试 1 次 → `extract_json` → `normalize_module_payload`；失败 `_fallback_module`。
- 概览：模块摘要 + README/清单 → 失败 `_fallback_overview`。
- 取消：每次调用前 `cancel_check()`，抛 `RunCancelled`。
- 指标：`llm.calls/okCalls/inputChars/outputChars`，`snapshot.files/modules/skipped`。

- [ ] **Step 4: `config.py` 加配置**

```python
spec_max_modules: int = 12
spec_max_files_per_module: int = 12
spec_max_file_chars: int = 4000
spec_concurrency: int = 2
```

- [ ] **Step 5: 跑测试**

Run: `cd backend && .\venv\Scripts\python.exe -m pytest tests/test_spec_service.py -q`
Expected: 7 passed

---

### Task 3: 九节渲染器

**Files:**
- Create: `backend/app/services/spec_renderer.py`
- Modify: `backend/app/services/renderers.py`
- Test: `backend/tests/test_renderers.py`

- [ ] **Step 1: 加失败测试**

```python
SPEC_RESULT = {
    "features": [], "highlights": [], "lowConfidence": ["src/order：LLM 降级"],
    "llm": {"provider": "xingyu", "model": "x", "prompt": "docrelease/v1",
            "confidence": 0.8, "inputChars": 1, "outputChars": 1, "glossaryHits": 0},
    "meta": {"runId": "r1", "repoName": "order-center", "version": "v1.1.0",
             "branch": "main", "headShort": "abc1234", "range": "v1.0.0..v1.1.0",
             "trigger": "手动触发", "generatedAt": "2026-10-19 10:00:00",
             "stats": {"commits": 3, "files": 4, "modules": 2, "added": 51, "removed": 16, "days": 2},
             "modules": ["src/order"], "pipeline": []},
    "spec": {
        "prompt": "spec/v1",
        "snapshot": {"ref": "v1.1.0", "files": 20, "modules": 2, "skipped": 0},
        "overview": {"name": "订单中心", "positioning": "交易履约", "problems": ["下单慢"], "scope": ["Web"]},
        "roles": [{"role": "买家", "scenarios": ["下单"]}],
        "architecture": {"stack": [{"layer": "后端", "tech": "Go", "note": ""}],
                         "modules": [{"name": "src/order", "responsibility": "订单"}],
                         "diagram": "flowchart LR\n A[\"前端\"] --> B[\"后端\"]"},
        "modules": [{
            "name": "backend/app/services", "responsibility": "订单服务", "changed": True, "degraded": False,
            "functions": [{"name": "创建订单", "logic": "POST /api/orders 写入 orders 表",
                           "roles": ["买家"], "priority": "P0"}],
            "flows": [{"title": "下单流程", "mermaid": "flowchart TD\n A[\"提交\"] --> B[\"落单\"]"}],
            "entities": [{"name": "Order", "table": "orders",
                          "fields": [{"name": "id", "type": "String(36)", "constraints": "PK", "note": "主键"}],
                          "relations": [{"target": "User", "label": "属于", "cardinality": "||--o{"}]}],
            "enums": [{"name": "OrderStatus", "values": ["paid", "closed"]}],
            "rules": [{"topic": "幂等", "points": ["重复提交返回同一订单"]}],
            "errorCodes": [{"scene": "参数非法", "code": "422", "ui": "提示"}],
            "nfr": {"performance": ["下单 P99 < 300ms"], "security": ["鉴权"],
                    "reliability": [], "deployment": [], "maintainability": [],
                    "extensibility": [], "compatibility": []},
        }],
        "degradedModules": [], "lowConfidence": [],
        "llm": {"calls": 2, "okCalls": 2, "inputChars": 100, "outputChars": 200},
    },
}


def test_product_spec_has_nine_sections_and_mermaid():
    text = r.render_document(SPEC_RESULT, {"tone": "business", "mask": False})
    for title in ["## 1. 项目概述", "## 2. 用户角色与使用场景", "## 3. 系统架构与技术栈",
                  "## 4. 功能清单及核心逻辑", "## 5. 核心流程", "## 6. 领域实体关系图",
                  "## 7. 领域实体清单", "## 8. 详细规则说明", "## 9. 非功能性需求"]:
        assert title in text
    assert "| 序号 | 功能简介 | 核心逻辑 | 涉及角色 | 优先级 |" in text
    assert "```mermaid" in text and "erDiagram" in text
    assert "创建订单" in text and "P0" in text


def test_product_spec_mask_hides_paths():
    text = r.render_document(SPEC_RESULT, {"tone": "business", "mask": True})
    assert "backend/app/services" not in text
    assert "…/app/services" in text


def test_document_falls_back_to_release_sections_without_spec():
    text = r.render_document(RESULT, {"tone": "business", "mask": False})
    assert "版本概览" in text and "## 1. 项目概述" not in text
```

- [ ] **Step 2: 实现 `spec_renderer.render_product_spec`**

固定九节标题、表格转义（`|`/换行）、全局编号、ER 聚合与标识符清洗、NFR 七主题、附录代码依据、mask。

- [ ] **Step 3: `renderers.render_document` 分发**

```python
def render_document(result: dict, opts: dict) -> str:
    if result.get("spec"):
        from app.services.spec_renderer import render_product_spec
        return render_product_spec(result, opts)
    return render_release_document(result, opts)
```

原函数体改名 `render_release_document`。

- [ ] **Step 4: 跑测试**

Run: `cd backend && .\venv\Scripts\python.exe -m pytest tests/test_renderers.py -q`
Expected: passed

---

### Task 4: 流水线接入与 trace

**Files:**
- Modify: `backend/app/services/pipeline_service.py`
- Modify: `backend/app/services/renderers.py`（trace 增加 spec 元数据）
- Modify: `backend/app/models/run.py`（STEP_NAMES[3]）
- Test: `backend/tests/test_pipeline.py`

- [ ] **Step 1: 步骤 3 并发**

```python
async def step4():
    rewrite_task = asyncio.create_task(
        llm_service.rewrite_changes(changeset, cancel_check=lambda: is_cancelled(run_id)))
    spec_task = asyncio.create_task(spec_service.generate_product_spec(
        repo.path, run.head_ref, repo.name, changeset,
        cancel_check=lambda: is_cancelled(run_id),
        log=lambda channel, tag, message: _log(run_id, state, channel, tag, message)))
    try:
        rewrite_outcome, spec = await asyncio.gather(rewrite_task, spec_task)
    except RunCancelled:
        for t in (rewrite_task, spec_task):
            t.cancel()
        await asyncio.gather(rewrite_task, spec_task, return_exceptions=True)
        raise
    except Exception:
        for t in (rewrite_task, spec_task):
            if not t.done():
                t.cancel()
        await asyncio.gather(rewrite_task, spec_task, return_exceptions=True)
        raise
    if rewrite_outcome["all_failed"]:
        raise ServiceError("LLM 改写全部失败，运行终止")
    ...
    return {"rewrite": rewrite_outcome, "spec": spec}
```

- [ ] **Step 2: 结果引用改造**

`outcome["rewrite"]...`、`result["spec"] = outcome["spec"]`；`final_status` 同时考虑 `spec["lowConfidence"]`。

- [ ] **Step 3: trace 元数据**

`render_trace` 增加：

```python
"spec": {
    "prompt": spec.get("prompt", ""),
    "modules": len(spec.get("modules") or []),
    "degraded": len(spec.get("degradedModules") or []),
    "files": (spec.get("snapshot") or {}).get("files", 0),
    "inputChars": (spec.get("llm") or {}).get("inputChars", 0),
    "outputChars": (spec.get("llm") or {}).get("outputChars", 0),
},
```

- [ ] **Step 4: 测试**

`test_pipeline.py` 增加 `assert run.result["spec"]["modules"]`、`assert "## 4. 功能清单及核心逻辑" in (target / "product-doc.md").read_text(...)`；步骤仍为 5。

Run: `cd backend && .\venv\Scripts\python.exe -m pytest tests/test_pipeline.py -q`
Expected: passed

---

### Task 5: 测试打桩与 API 断言

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_api_runs.py`
- Modify: `backend/e2e_smoke.py`

- [ ] **Step 1: conftest 分流**

系统提示词含 `产品说明书生成引擎（spec/v1）`：
- 用户提示以 `模块：` 开头 → 返回模块 JSON（responsibility/functions/flows/entities/enums/rules/errorCodes/nfr）。
- 否则 → 返回 overview JSON（overview/roles/architecture）。

其余返回原 features JSON。

- [ ] **Step 2: `_slow_chat` 与 e2e 打桩同步分流**

- [ ] **Step 3: 断言更新**

`test_api_runs.py`：`assert "## 4. 功能清单及核心逻辑" in doc.text`。
`e2e_smoke.py`：document 产物同时断言九节标题与 ` ```mermaid `。

Run: `cd backend && .\venv\Scripts\python.exe -m pytest tests -q`
Expected: 全部 passed

---

### Task 6: 前端 mermaid

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/render/artifacts.ts`
- Modify: `frontend/src/components/OutputPanel.vue`
- Modify: `frontend/src/data/steps.ts`

- [ ] **Step 1: 安装依赖**

Run: `cd frontend && npm install mermaid@^11`
Expected: package.json/package-lock 更新

- [ ] **Step 2: `artifacts.ts` 自定义 renderer**

```ts
const renderer = new marked.Renderer()
renderer.code = ({ text, lang }) => {
  if ((lang || '').trim().toLowerCase() === 'mermaid') {
    return `<div class="mermaid">${escapeHtml(text)}</div>`
  }
  return `<pre><code>${escapeHtml(text)}</code></pre>`
}
return DOMPurify.sanitize(marked.parse(md, { renderer }) as string)
```

保留原有代码块渲染语义（可用 marked 默认行为），仅拦截 mermaid。

- [ ] **Step 3: `OutputPanel.vue` 渲染**

`flush: 'post'` 监听 `[activeKind, mdHtml]`，对 `.mermaid:not([data-processed])` 逐块 `mermaid.run`；失败替换为 `<pre class="mermaid-fallback">`；`securityLevel:'strict'`；CSS 自适应。

- [ ] **Step 4: `steps.ts` 更新**

第 4 步名称改「LLM 业务化改写与产品说明书生成」，read/write 说明同步。

- [ ] **Step 5: 构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功

---

### Task 7: 文档同步

**Files:**
- Modify: `doc-release/docs/产品说明.md`

- [ ] **Step 1:** 更新 4.2 步骤 3、4.4 产物渲染、5.3 流水线图、5.6 渲染流程、7.2 result 结构、8.9 渲染规则、9.1/9.2 性能与安全、附录代码依据。
- [ ] **Step 2:** 全文检索「八章节」「八节」「五步流水线」相关描述，确保与新实现一致。

---

### Task 8: 全量验证

- [ ] **Step 1: 后端测试**

Run: `cd backend && .\venv\Scripts\python.exe -m pytest tests -q`
Expected: 全部 passed（原 95 + 新增）

- [ ] **Step 2: 离线 E2E**

Run: `cd backend && .\venv\Scripts\python.exe e2e_smoke.py`
Expected: 三场景通过，产物 3 份，document 含九节与 mermaid

- [ ] **Step 3: 前端构建**

Run: `cd frontend && npm run build`
Expected: 成功

- [ ] **Step 4: 手工验证**

启动后端 + 前端，跑一次示例场景，确认：
- 产品说明 tab 渲染九节；
- 流程图/ER 图显示为图形；
- 手动篡改一处 mermaid 语法后该图降级为代码块，其余章节正常。
