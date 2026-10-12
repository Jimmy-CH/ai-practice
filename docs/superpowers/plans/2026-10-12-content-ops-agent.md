# AI 内容运营 Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在独立应用中交付可从主题、文档、CI/CD 和 Git 上下文生成、编辑、审核及下载公告、FAQ、海报的内容运营 Agent。

**Architecture:** 新建 `content-ops-agent`，后端使用 FastAPI、异步 SQLAlchemy 与项目级 RAG；前端使用 Vue 3、Pinia、Element Plus。生成任务和导出通过服务边界隔离，发布仅实现可测试的模拟适配器。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2、aiosqlite、Pydantic Settings、LangChain/Chroma、httpx、PyPDF、python-docx、OpenAI-compatible LLM/image client、pytest；Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、Axios、Vitest。

---

## 文件结构

- `content-ops-agent/backend/app/main.py`：应用生命周期、数据库初始化、路由和 CORS。
- `content-ops-agent/backend/app/models/`：项目、来源、资产版本、审核、交付、审计 ORM 模型。
- `content-ops-agent/backend/app/services/`：导入、检索、生成、审核、导出、发布和安全服务。
- `content-ops-agent/backend/app/api/`：请求/响应 schema 与 API 路由。
- `content-ops-agent/backend/tests/`：服务、API 和端到端测试。
- `content-ops-agent/frontend/src/`：类型、API 客户端、Pinia store、路由与业务页面。
- `content-ops-agent/frontend/src/views/`：项目、来源、创作、审核与交付界面。

### Task 1: 建立可运行的后端骨架

**Files:**
- Create: `content-ops-agent/backend/requirements.txt`
- Create: `content-ops-agent/backend/app/config.py`
- Create: `content-ops-agent/backend/app/database.py`
- Create: `content-ops-agent/backend/app/main.py`
- Create: `content-ops-agent/backend/app/api/router.py`
- Create: `content-ops-agent/backend/tests/conftest.py`
- Create: `content-ops-agent/backend/tests/test_health.py`

- [ ] **Step 1: 写失败的健康检查测试**

```python
@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd content-ops-agent/backend; pytest tests/test_health.py -v`
Expected: FAIL，缺少应用模块。

- [ ] **Step 3: 实现最小应用与测试夹具**

```python
# app/main.py
app = FastAPI(title="Content Ops Agent")
app.include_router(api_router, prefix="/api")
@app.get("/health")
async def health() -> dict[str, str]: return {"status": "ok"}
```

`config.py` 使用 `BaseSettings` 定义 `DATABASE_URL`、`ALLOWED_ORIGINS`、`UPLOAD_DIR`、`WEBHOOK_SECRET` 和模型配置；`database.py` 暴露异步 `engine`、`AsyncSessionLocal`、`Base`、`get_db`。requirements 锁定 FastAPI、SQLAlchemy、aiosqlite、pydantic-settings、python-multipart、httpx、pytest、pytest-asyncio。

- [ ] **Step 4: 运行测试并确认通过**

Run: `pytest tests/test_health.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add content-ops-agent/backend
git commit -m "feat: bootstrap content ops backend"
```

### Task 2: 实现领域模型与项目 API

**Files:**
- Create: `content-ops-agent/backend/app/models/content.py`
- Create: `content-ops-agent/backend/app/schemas/projects.py`
- Create: `content-ops-agent/backend/app/api/projects.py`
- Modify: `content-ops-agent/backend/app/api/router.py`
- Modify: `content-ops-agent/backend/app/main.py`
- Create: `content-ops-agent/backend/tests/test_projects.py`

- [ ] **Step 1: 写失败的项目创建/读取 API 测试**

```python
async def test_create_project(client: AsyncClient) -> None:
    payload = {"name": "秋季发布", "theme": "全新搜索", "audience": "存量客户", "tone": "专业"}
    created = await client.post("/api/projects", json=payload)
    assert created.status_code == 201
    project = created.json()
    assert project["theme"] == "全新搜索"
    listed = await client.get("/api/projects")
    assert [item["id"] for item in listed.json()] == [project["id"]]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_projects.py::test_create_project -v`
Expected: FAIL，`/api/projects` 未注册。

- [ ] **Step 3: 实现模型和路由**

`content.py` 定义 `ContentProject`、`Source`、`KnowledgeChunk`、`ContentAsset`、`AssetVersion`、`Review`、`DeliveryJob`、`AuditLog`；所有表使用 UUID 主键和 `created_at`/`updated_at`。`AssetStatus` 固定为 `draft`、`pending_review`、`approved`、`rejected`，`AssetKind` 固定为 `announcement`、`faq`、`poster`。在 lifespan 中导入模型并执行 `Base.metadata.create_all`。项目 API 提供 `POST /projects`、`GET /projects`、`GET /projects/{id}`。

```python
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    theme: str = Field(min_length=1, max_length=2000)
    audience: str = Field(min_length=1, max_length=200)
    tone: str = Field(min_length=1, max_length=80)
```

- [ ] **Step 4: 运行项目测试**

Run: `pytest tests/test_projects.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add content-ops-agent/backend
git commit -m "feat: add content project domain"
```

### Task 3: 实现文档、Git 与 Webhook 来源导入

**Files:**
- Create: `content-ops-agent/backend/app/services/sources.py`
- Create: `content-ops-agent/backend/app/services/webhooks.py`
- Create: `content-ops-agent/backend/app/schemas/sources.py`
- Create: `content-ops-agent/backend/app/api/sources.py`
- Modify: `content-ops-agent/backend/app/api/router.py`
- Create: `content-ops-agent/backend/tests/test_sources.py`
- Create: `content-ops-agent/backend/tests/test_webhooks.py`

- [ ] **Step 1: 写失败的导入与幂等 Webhook 测试**

```python
async def test_duplicate_webhook_is_idempotent(client: AsyncClient, project_id: str, signature: str) -> None:
    body = {"event_id": "build-100", "version": "1.2.0", "summary": "修复搜索"}
    first = await client.post(f"/api/projects/{project_id}/webhooks/cicd", json=body, headers={"X-Signature": signature})
    second = await client.post(f"/api/projects/{project_id}/webhooks/cicd", json=body, headers={"X-Signature": signature})
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_sources.py tests/test_webhooks.py -v`
Expected: FAIL，来源路由不存在。

- [ ] **Step 3: 实现来源服务**

限制上传 `pdf`、`docx`、`md`、`txt` 且大小不超过配置的 `MAX_UPLOAD_BYTES`；计算 SHA-256 并拒绝不允许的 MIME。将文件解析为纯文本，存储 `Source` 和 `KnowledgeChunk`。实现 `POST /projects/{id}/sources/files`、`POST /projects/{id}/sources/git`、`POST /projects/{id}/webhooks/cicd`。Webhook 使用 `hmac.compare_digest` 比较 `sha256=` 签名，拒绝超过五分钟的 `X-Timestamp`，以 `event_id` 建立唯一键。Git 服务只经 `httpx.AsyncClient` 调用配置的 Git provider，并由测试 fake client 替代。

- [ ] **Step 4: 运行来源测试**

Run: `pytest tests/test_sources.py tests/test_webhooks.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add content-ops-agent/backend
git commit -m "feat: import project sources securely"
```

### Task 4: 实现检索与三类内容生成服务

**Files:**
- Create: `content-ops-agent/backend/app/services/retrieval.py`
- Create: `content-ops-agent/backend/app/services/generation.py`
- Create: `content-ops-agent/backend/app/schemas/assets.py`
- Create: `content-ops-agent/backend/app/api/assets.py`
- Modify: `content-ops-agent/backend/app/api/router.py`
- Create: `content-ops-agent/backend/tests/test_generation.py`

- [ ] **Step 1: 写失败的生成测试**

```python
async def test_generate_assets_persists_citations(client: AsyncClient, project_with_source: str) -> None:
    response = await client.post(f"/api/projects/{project_with_source}/generate", json={"kinds": ["announcement", "faq", "poster"]})
    assert response.status_code == 202
    assets = response.json()["assets"]
    assert {asset["kind"] for asset in assets} == {"announcement", "faq", "poster"}
    assert all(asset["version"]["citations"] for asset in assets)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_generation.py -v`
Expected: FAIL，生成端点不存在。

- [ ] **Step 3: 实现可注入生成器**

定义 `Retriever.search(project_id, query) -> list[Citation]` 和 `ContentGenerator.generate(kind, context) -> GeneratedAsset` 协议。生产实现调用向量索引和 OpenAI-compatible 客户端；测试实现返回固定内容。检索为空时返回 422 及 `code="INSUFFICIENT_EVIDENCE"`。公告内容为 `{title, summary, body, call_to_action}`，FAQ 为 `{items:[{question,answer}]}`，海报为 `{headline, highlights, call_to_action, image_prompt}`。生成图像失败时保留海报文案、记录 `image_status="failed"` 并允许重试。生成端点保存 `ContentAsset(draft)`、`AssetVersion` 及引用。

- [ ] **Step 4: 运行生成测试**

Run: `pytest tests/test_generation.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add content-ops-agent/backend
git commit -m "feat: generate traced content assets"
```

### Task 5: 实现版本、审核、导出与模拟发布

**Files:**
- Create: `content-ops-agent/backend/app/services/reviews.py`
- Create: `content-ops-agent/backend/app/services/exporters.py`
- Create: `content-ops-agent/backend/app/services/publishers.py`
- Create: `content-ops-agent/backend/app/api/reviews.py`
- Create: `content-ops-agent/backend/app/api/delivery.py`
- Modify: `content-ops-agent/backend/app/api/router.py`
- Create: `content-ops-agent/backend/tests/test_review_delivery.py`

- [ ] **Step 1: 写失败的状态机测试**

```python
async def test_only_approved_version_can_be_downloaded(client: AsyncClient, asset_id: str) -> None:
    pending = await client.post(f"/api/assets/{asset_id}/submit-review")
    assert pending.status_code == 200
    denied = await client.get(f"/api/assets/{asset_id}/download?format=html")
    assert denied.status_code == 409
    approved = await client.post(f"/api/assets/{asset_id}/reviews", json={"decision": "approved", "comment": "准确"})
    assert approved.status_code == 200
    downloaded = await client.get(f"/api/assets/{asset_id}/download?format=html")
    assert downloaded.status_code == 200
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_review_delivery.py -v`
Expected: FAIL，审核端点不存在。

- [ ] **Step 3: 实现状态转换和交付服务**

只允许 `draft → pending_review`、`pending_review → approved|rejected`；每次编辑以 `POST /assets/{id}/versions` 创建新版本并回到 draft。导出器根据 kind 验证格式：公告/FAQ 为 markdown/html/docx，海报为 png/pdf。`PublisherAdapter` 定义 `validate`、`publish`、`status`；`MockPublisher` 创建 `DeliveryJob` 并返回 `completed`。所有操作写 `AuditLog`。暴露编辑、提交审核、审核、下载、创建交付任务和查询任务端点。

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_review_delivery.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add content-ops-agent/backend
git commit -m "feat: add review delivery workflow"
```

### Task 6: 建立 Vue 前端基础设施

**Files:**
- Create: `content-ops-agent/frontend/package.json`
- Create: `content-ops-agent/frontend/src/main.ts`
- Create: `content-ops-agent/frontend/src/App.vue`
- Create: `content-ops-agent/frontend/src/router/index.ts`
- Create: `content-ops-agent/frontend/src/api/client.ts`
- Create: `content-ops-agent/frontend/src/types/content.ts`
- Create: `content-ops-agent/frontend/src/stores/projects.ts`
- Create: `content-ops-agent/frontend/src/views/ProjectListView.vue`
- Create: `content-ops-agent/frontend/src/views/ProjectDetailView.vue`
- Create: `content-ops-agent/frontend/src/views/ProjectListView.spec.ts`

- [ ] **Step 1: 写失败的项目列表组件测试**

```ts
it('renders project names returned by the store', async () => {
  mount(ProjectListView, { global: { plugins: [createTestingPinia({ initialState: { projects: { items: [{ id: '1', name: '秋季发布' }] } } })] } })
  expect(await screen.findByText('秋季发布')).toBeTruthy()
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd content-ops-agent/frontend; npm run test -- ProjectListView.spec.ts`
Expected: FAIL，前端项目尚不存在。

- [ ] **Step 3: 实现 Vite、路由和项目 store**

配置 Vue、Vue Router、Pinia、Element Plus、Axios、Vitest、Vue Test Utils、Testing Library。`client.ts` 将 `VITE_API_BASE_URL` 作为 baseURL；项目 store 实现 `load`、`create`、`selectedProject`。路由包含 `/projects`、`/projects/:id/sources`、`/projects/:id/workspace`、`/projects/:id/review`、`/projects/:id/delivery`。

- [ ] **Step 4: 运行单测和构建**

Run: `npm run test -- ProjectListView.spec.ts && npm run build`
Expected: PASS，构建无 TypeScript 错误。

- [ ] **Step 5: 提交**

```bash
git add content-ops-agent/frontend
git commit -m "feat: bootstrap content ops frontend"
```

### Task 7: 实现来源中心与生成操作

**Files:**
- Create: `content-ops-agent/frontend/src/views/SourceCenterView.vue`
- Create: `content-ops-agent/frontend/src/components/SourceUpload.vue`
- Create: `content-ops-agent/frontend/src/components/GenerateAssetsDialog.vue`
- Create: `content-ops-agent/frontend/src/views/SourceCenterView.spec.ts`

- [ ] **Step 1: 写失败的来源提交测试**

```ts
it('sends the selected file for the current project', async () => {
  const file = new File(['版本说明'], 'release.md', { type: 'text/markdown' })
  await userEvent.upload(screen.getByLabelText('上传资料'), file)
  await userEvent.click(screen.getByRole('button', { name: '导入' }))
  expect(uploadSource).toHaveBeenCalledWith('project-1', file)
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `npm run test -- SourceCenterView.spec.ts`
Expected: FAIL，组件不存在。

- [ ] **Step 3: 实现来源与生成页面**

页面显示活动主题、来源状态和解析失败原因；提供文件上传、CI/CD 载荷模拟提交、Git 范围输入。生成弹窗固定三类资产复选项且默认全选，提交 `/generate` 后跳转创作工作台。为文件类型、大小和 Webhook 签名错误显示 API 的具体错误信息。

- [ ] **Step 4: 运行测试和构建**

Run: `npm run test -- SourceCenterView.spec.ts && npm run build`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add content-ops-agent/frontend
git commit -m "feat: add source import workflow"
```

### Task 8: 实现创作、审核与交付工作台

**Files:**
- Create: `content-ops-agent/frontend/src/views/WorkspaceView.vue`
- Create: `content-ops-agent/frontend/src/components/AnnouncementEditor.vue`
- Create: `content-ops-agent/frontend/src/components/FaqEditor.vue`
- Create: `content-ops-agent/frontend/src/components/PosterEditor.vue`
- Create: `content-ops-agent/frontend/src/views/ReviewView.vue`
- Create: `content-ops-agent/frontend/src/views/DeliveryView.vue`
- Create: `content-ops-agent/frontend/src/views/WorkspaceView.spec.ts`

- [ ] **Step 1: 写失败的审核前下载禁用测试**

```ts
it('disables download before asset approval', () => {
  mount(WorkspaceView, { props: { asset: { id: 'a1', kind: 'announcement', status: 'pending_review' } } })
  expect(screen.getByRole('button', { name: '下载' })).toBeDisabled()
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `npm run test -- WorkspaceView.spec.ts`
Expected: FAIL，工作台组件不存在。

- [ ] **Step 3: 实现资产编辑和交付 UI**

按资产类型渲染编辑器；保存时创建版本并展示引用折叠面板。审核页支持通过/驳回及评论，按 API 状态限制按钮。已通过资产提供格式选择和下载；交付页可创建、查看模拟发布任务。海报编辑器提供底图预览、标题/卖点/行动号召文本覆盖层和 PNG/PDF 下载。

- [ ] **Step 4: 运行测试和构建**

Run: `npm run test -- WorkspaceView.spec.ts && npm run build`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add content-ops-agent/frontend
git commit -m "feat: add asset review and delivery workspace"
```

### Task 9: 端到端验证、配置与使用文档

**Files:**
- Create: `content-ops-agent/backend/.env.example`
- Create: `content-ops-agent/backend/tests/test_e2e_content_flow.py`
- Create: `content-ops-agent/README.md`
- Modify: `.gitignore`

- [ ] **Step 1: 写失败的端到端流程测试**

```python
async def test_content_flow(client: AsyncClient, fake_generator: None) -> None:
    project = await create_project(client)
    await upload_markdown(client, project["id"], "release.md", "新增智能搜索")
    assets = await generate_all(client, project["id"])
    await submit_and_approve(client, assets["announcement"]["id"])
    response = await client.get(f'/api/assets/{assets["announcement"]["id"]}/download?format=html')
    assert response.status_code == 200
    assert "智能搜索" in response.text
```

- [ ] **Step 2: 运行端到端测试**

Run: `pytest tests/test_e2e_content_flow.py -v`
Expected: PASS；若失败，记录失败的端点和断言，再以最小改动修复后重新运行。

- [ ] **Step 3: 补齐测试发现的实现缺口并编写配置文档**

`.env.example` 必须包含 `DATABASE_URL`、`UPLOAD_DIR`、`ALLOWED_ORIGINS`、`WEBHOOK_SECRET`、`GIT_API_BASE_URL`、`LLM_BASE_URL`、`LLM_API_KEY`、`IMAGE_API_KEY`、`MAX_UPLOAD_BYTES`。README 提供 Windows PowerShell 下的安装、配置、前后端启动、模拟 Webhook 命令、测试运行方式和真实渠道适配边界。`.gitignore` 排除上传文件、SQLite、Chroma 数据、`.env` 和前端构建产物。

- [ ] **Step 4: 运行全量验证**

Run: `cd content-ops-agent/backend; pytest -v; cd ../frontend; npm run test && npm run build`
Expected: 后端 pytest 全通过，前端测试和生产构建全通过。

- [ ] **Step 5: 提交**

```bash
git add content-ops-agent .gitignore
git commit -m "docs: document content ops agent setup"
```
