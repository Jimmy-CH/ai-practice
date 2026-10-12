# 证据约束内容生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 DeepSeek 和项目资料证据替换占位文本拼接，生成可追溯且资料不足时拒答的内容资产。

**Architecture:** `retrieval.py` 负责确定性证据选择，`generation.py` 负责可注入的 DeepSeek 客户端与 JSON 校验，API 只协调并持久化校验后的结果。

**Tech Stack:** FastAPI、SQLAlchemy、httpx、Pydantic、DeepSeek OpenAI-compatible API、pytest。

---

### Task 1: 证据选择服务

**Files:**
- Create: `content-ops-agent/backend/app/services/retrieval.py`
- Create: `content-ops-agent/backend/tests/test_retrieval.py`

- [ ] 写失败测试，证明主题关键词匹配的段落排名在无关段落之前：
```python
def test_select_evidence_prefers_theme_terms():
    chunks = split_and_rank("搜索功能上线。\n\n公司团建通知。", ["搜索"])
    assert chunks[0].text == "搜索功能上线。"
```
- [ ] 运行 `cd content-ops-agent/backend; python -m pytest tests/test_retrieval.py -v`，确认失败。
- [ ] 实现 `Evidence`、`split_and_rank(text, keywords)` 与 `select_project_evidence(sources, keywords, limit)`；按空行/句末切分，按不区分大小写的关键词出现次数排序，最多返回配置的数量。
- [ ] 重跑测试，确认通过并提交 `feat: rank source evidence`。

### Task 2: DeepSeek 生成器与配置

**Files:**
- Modify: `content-ops-agent/backend/app/config.py`
- Create: `content-ops-agent/backend/app/services/generation.py`
- Create: `content-ops-agent/backend/tests/test_deepseek_generation.py`

- [ ] 写失败测试，以 FakeTransport 返回 JSON，断言 `DeepSeekGenerator.generate` 请求包含证据与“不得使用证据外事实”。
- [ ] 运行 `python -m pytest tests/test_deepseek_generation.py -v`，确认失败。
- [ ] 添加 `deepseek_api_key`、`deepseek_base_url=https://api.deepseek.com`、`deepseek_model=deepseek-chat`、`max_evidence_chunks=6` 配置；实现 `Generator` 协议与 `DeepSeekGenerator`，使用 httpx POST `/chat/completions`，请求 JSON object 输出并解析公告、FAQ、海报。
- [ ] 对空 API Key、超时、非 JSON、缺字段抛出明确的领域异常；重跑测试并提交 `feat: add DeepSeek evidence generator`。

### Task 3: 替换占位生成 API

**Files:**
- Modify: `content-ops-agent/backend/app/api/generation.py`
- Modify: `content-ops-agent/backend/tests/test_generation.py`
- Create: `content-ops-agent/backend/tests/test_generation_failures.py`

- [ ] 写失败测试，断言来源不足时 `POST /generate` 返回 422 且数据库没有新资产；断言 FakeGenerator 返回未知来源 ID 时也拒绝保存。
- [ ] 运行对应 pytest，确认失败。
- [ ] 在 API 中获取项目来源、选择 Top-K 证据、调用注入生成器；仅接受证据集合内的引用，验证三个资产类型与字段后再一次性保存 `ContentAsset`。
- [ ] 证据不足返回 `422 {"detail":"需补充资料"}`；生成服务失败返回 502；重跑测试并提交 `feat: generate assets from verified evidence`。

### Task 4: 配置样例与全量验证

**Files:**
- Create: `content-ops-agent/backend/.env.example`
- Modify: `content-ops-agent/README.md`

- [ ] 写入 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`MAX_EVIDENCE_CHUNKS` 样例值，并在 README 说明缺少 Key 时生成拒绝执行、资料不足时不会生成资产。
- [ ] 运行 `cd content-ops-agent/backend; python -m pytest tests -v`。
- [ ] 运行 `cd content-ops-agent/frontend; npm run build`。
- [ ] 确认全部通过后提交 `docs: document evidence grounded generation`。
