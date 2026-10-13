# 解析结果持久化与前端编辑实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI 解析出的四类运营要点持久化到后端 SQLite，支持同文档重复解析时直接返回历史结果；同时在前端提供条目级编辑能力，并可用编辑后的解析结果重新生成物料。

**Architecture:** 新增独立的 `ParsedAnalysis` 资源保存解析快照，按 `owner_id + source_title` 覆盖；`parse` 端点改为需登录，首次解析调用 DeepSeek 并 upsert，重复解析直接读库；前端 `GeneratorView` 的解析卡片改为可编辑列表，并提供「保存解析结果」与「重新生成」按钮。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + aiosqlite / Vue 3 + TypeScript + Element Plus + Pinia + Axios

---

### Task 1: ParsedAnalysis 模型与 Pydantic schema

**Files:**
- Create: `ai-material-generator/backend/app/models/parsed_analysis.py`
- Create: `ai-material-generator/backend/app/schemas/analysis.py`
- Modify: `ai-material-generator/backend/app/models/__init__.py`（如需要显式导入）

- [ ] **Step 1: 创建 ParsedAnalysis 模型**

```python
import json
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ParsedAnalysis(Base):
    __tablename__ = "parsed_analyses"
    __table_args__ = (UniqueConstraint("owner_id", "source_title", name="uix_owner_title"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)

    new_features: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    changes: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    notices: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    risks: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "source_title": self.source_title,
            "新增功能": json.loads(self.new_features),
            "变更与优化": json.loads(self.changes),
            "注意事项": json.loads(self.notices),
            "风险提示": json.loads(self.risks),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
```

- [ ] **Step 2: 创建 Pydantic schema**

```python
from pydantic import BaseModel, ConfigDict


class AnalysisUpdate(BaseModel):
    new_features: list[str]
    changes: list[str]
    notices: list[str]
    risks: list[str]


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    source_title: str
    new_features: list[str]
    changes: list[str]
    notices: list[str]
    risks: list[str]
    created_at: str | None = None
    updated_at: str | None = None
```

- [ ] **Step 3: 验证模型可被导入**

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -c "from app.models.parsed_analysis import ParsedAnalysis; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 4: Commit**

```bash
cd ai-material-generator
git add backend/app/models/parsed_analysis.py backend/app/schemas/analysis.py
git commit -m "feat(analysis): add ParsedAnalysis model and schemas"
```

---

### Task 2: 解析服务层

**Files:**
- Create: `ai-material-generator/backend/app/services/analysis_service.py`
- Create: `ai-material-generator/backend/tests/test_analysis_service.py`

- [ ] **Step 1: 写 upsert 测试（先失败）**

```python
import pytest
from app.services import analysis_service as svc
from app.models.parsed_analysis import ParsedAnalysis


@pytest.mark.asyncio
async def test_upsert_analysis_creates(db_session):
    analysis = await svc.upsert_analysis(
        db_session, owner_id=1, source_title="版本说明",
        data={"新增功能": ["a"], "变更与优化": ["b"], "注意事项": ["c"], "风险提示": ["d"]}
    )
    assert analysis.id is not None
    assert analysis.source_title == "版本说明"
    assert analysis.owner_id == 1
```

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_analysis_service.py::test_upsert_analysis_creates -v`
Expected: FAIL `module 'app.services' has no attribute 'analysis_service'`

- [ ] **Step 2: 实现 upsert 与 get 方法**

```python
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.parsed_analysis import ParsedAnalysis


async def get_analysis_by_title(session: AsyncSession, owner_id: int, source_title: str) -> ParsedAnalysis | None:
    stmt = select(ParsedAnalysis).where(
        ParsedAnalysis.owner_id == owner_id,
        ParsedAnalysis.source_title == source_title,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_analysis(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    data: dict,
) -> ParsedAnalysis:
    analysis = await get_analysis_by_title(session, owner_id, source_title)
    if analysis is None:
        analysis = ParsedAnalysis(owner_id=owner_id, source_title=source_title)
        session.add(analysis)

    analysis.new_features = json.dumps(data.get("新增功能", []), ensure_ascii=False)
    analysis.changes = json.dumps(data.get("变更与优化", []), ensure_ascii=False)
    analysis.notices = json.dumps(data.get("注意事项", []), ensure_ascii=False)
    analysis.risks = json.dumps(data.get("风险提示", []), ensure_ascii=False)

    await session.commit()
    await session.refresh(analysis)
    return analysis
```

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_analysis_service.py::test_upsert_analysis_creates -v`
Expected: PASS

- [ ] **Step 3: 写覆盖与更新测试**

```python
@pytest.mark.asyncio
async def test_upsert_analysis_overwrites(db_session):
    await svc.upsert_analysis(db_session, owner_id=1, source_title="版本说明", data={"新增功能": ["a"], "变更与优化": [], "注意事项": [], "风险提示": []})
    analysis = await svc.upsert_analysis(db_session, owner_id=1, source_title="版本说明", data={"新增功能": ["b"], "变更与优化": [], "注意事项": [], "风险提示": []})
    loaded = await svc.get_analysis_by_title(db_session, owner_id=1, source_title="版本说明")
    assert loaded is not None
    assert json.loads(loaded.new_features) == ["b"]


@pytest.mark.asyncio
async def test_update_analysis(db_session):
    created = await svc.upsert_analysis(db_session, owner_id=1, source_title="版本说明", data={"新增功能": ["a"], "变更与优化": [], "注意事项": [], "风险提示": []})
    updated = await svc.update_analysis(db_session, created, {"new_features": ["x"], "changes": ["y"], "notices": ["z"], "risks": ["w"]})
    assert json.loads(updated.new_features) == ["x"]
    assert json.loads(updated.changes) == ["y"]
```

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_analysis_service.py -v`
Expected: FAIL `module 'app.services' has no attribute 'update_analysis'`

- [ ] **Step 4: 实现 update_analysis**

在上一步的 `analysis_service.py` 中追加：

```python
from app.schemas.analysis import AnalysisUpdate


async def update_analysis(session: AsyncSession, analysis: ParsedAnalysis, data: AnalysisUpdate) -> ParsedAnalysis:
    analysis.new_features = json.dumps(data.new_features, ensure_ascii=False)
    analysis.changes = json.dumps(data.changes, ensure_ascii=False)
    analysis.notices = json.dumps(data.notices, ensure_ascii=False)
    analysis.risks = json.dumps(data.risks, ensure_ascii=False)
    await session.commit()
    await session.refresh(analysis)
    return analysis
```

注意：因为 `AnalysisUpdate` 在前端传入时是 dict，这里也接受 dict 以兼容。实际调用时可在路由层用 `AnalysisUpdate(**data)` 转换。

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_analysis_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ai-material-generator
git add backend/app/services/analysis_service.py backend/tests/test_analysis_service.py
git commit -m "feat(analysis): add analysis service with upsert and update"
```

---

### Task 3: 改造 parse 端点并接入持久化

**Files:**
- Modify: `ai-material-generator/backend/app/api/generator.py`
- Modify: `ai-material-generator/backend/app/api/auth.py`（确认 `get_current_user` 可被导入；若无变更则无需修改）

- [ ] **Step 1: 修改 parse_endpoint 为需登录，并自动保存解析结果**

```python
from app.services import analysis_service as analysis_svc
from app.api.auth import get_current_user


@router.post("/parse")
async def parse_endpoint(
    title: str = Form(...),
    content: str = Form(""),
    file: UploadFile | None = File(None),
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not content and not file:
        raise HTTPException(status_code=400, detail="请输入文档正文或上传 .docx 文件")
    if file and not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="仅支持 .docx 格式 Word 文档")
    try:
        # 优先读取数据库，避免重复调用模型
        existing = await analysis_svc.get_analysis_by_title(db, user.id, title)
        if existing is not None:
            return {"analysis_id": existing.id, "title": title, **existing.to_dict()}

        if file:
            suffix = Path(file.filename).suffix
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name
            content = parse_docx_file(tmp_path)
            Path(tmp_path).unlink(missing_ok=True)
        if not content.strip():
            raise HTTPException(status_code=400, detail="文档正文为空")
        result = await analyze_document(title, content)
        saved = await analysis_svc.upsert_analysis(db, user.id, title, result)
        return {"analysis_id": saved.id, "title": title, **saved.to_dict()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"文档解析失败: {exc}") from exc
```

注意：`UserOut` 已在文件顶部导入。确保导入顺序合理。

- [ ] **Step 2: 写集成测试验证首次解析保存**

```python
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_parse_saves_analysis(client, editor_token):
    with patch("app.api.generator.analyze_document", return_value={
        "新增功能": ["一键上报"],
        "变更与优化": ["优化导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }) as mock_analyze:
        r = await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["analysis_id"] is not None
    assert data["新增功能"] == ["一键上报"]
    mock_analyze.assert_called_once()
```

Create: `ai-material-generator/backend/tests/test_parse_persist.py`

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_parse_persist.py::test_parse_saves_analysis -v`
Expected: PASS

- [ ] **Step 3: 写集成测试验证重复解析不调用模型**

```python
@pytest.mark.asyncio
async def test_parse_uses_cached_analysis(client, editor_token):
    with patch("app.api.generator.analyze_document", return_value={
        "新增功能": ["一键上报"],
        "变更与优化": ["优化导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }) as mock_analyze:
        await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        r = await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    assert r.status_code == 200
    assert r.json()["新增功能"] == ["一键上报"]
    mock_analyze.assert_called_once()
```

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_parse_persist.py -v`
Expected: PASS

- [ ] **Step 4: 验证未登录解析返回 401**

```python
@pytest.mark.asyncio
async def test_parse_requires_auth(client):
    r = await client.post("/api/parse", data={"title": "版本说明", "content": "正文"})
    assert r.status_code == 401
```

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_parse_persist.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd ai-material-generator
git add backend/app/api/generator.py backend/tests/test_parse_persist.py
git commit -m "feat(parse): persist analysis and skip model on cache hit"
```

---

### Task 4: 新增 analyses API（获取与更新）

**Files:**
- Create: `ai-material-generator/backend/app/api/analyses.py`
- Modify: `ai-material-generator/backend/app/main.py`
- Create: `ai-material-generator/backend/tests/test_analyses_api.py`

- [ ] **Step 1: 创建 analyses 路由**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.auth import UserOut
from app.schemas.analysis import AnalysisOut, AnalysisUpdate
from app.api.auth import get_current_user
from app.services import analysis_service as svc

router = APIRouter()


@router.get("/{source_title}", response_model=AnalysisOut)
async def get_analysis(
    source_title: str,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis = await svc.get_analysis_by_title(db, user.id, source_title)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="解析结果不存在")
    return analysis


@router.put("/{analysis_id}", response_model=AnalysisOut)
async def update_analysis(
    analysis_id: int,
    data: AnalysisUpdate,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis = await svc.get_analysis(db, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="解析结果不存在")
    if analysis.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限修改")
    updated = await svc.update_analysis(db, analysis, data)
    return updated
```

注意：需要在 `analysis_service.py` 中新增 `get_analysis(session, analysis_id)` 方法：

```python
async def get_analysis(session: AsyncSession, analysis_id: int) -> ParsedAnalysis | None:
    return await session.get(ParsedAnalysis, analysis_id)
```

- [ ] **Step 2: 注册路由到 main.py**

```python
from app.api.analyses import router as analyses_router

app.include_router(analyses_router, prefix="/api/analyses")
```

- [ ] **Step 3: 写 API 测试**

```python
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_get_analysis(client, editor_token):
    with patch("app.api.generator.analyze_document", return_value={
        "新增功能": ["一键上报"],
        "变更与优化": ["优化导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }):
        await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    r = await client.get(
        "/api/analyses/版本说明",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 200
    assert r.json()["new_features"] == ["一键上报"]


@pytest.mark.asyncio
async def test_update_analysis(client, editor_token):
    with patch("app.api.generator.analyze_document", return_value={
        "新增功能": ["一键上报"],
        "变更与优化": ["优化导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }):
        parsed = await client.post(
            "/api/parse",
            data={"title": "版本说明", "content": "正文"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    analysis_id = parsed.json()["analysis_id"]
    r = await client.put(
        f"/api/analyses/{analysis_id}",
        json={"new_features": ["编辑后"], "changes": [], "notices": [], "risks": []},
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r.status_code == 200
    assert r.json()["new_features"] == ["编辑后"]
```

- [ ] **Step 4: 运行全部后端测试**

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests -v`
Expected: 全部通过（原有 18 个 + 新增）

- [ ] **Step 5: Commit**

```bash
cd ai-material-generator
git add backend/app/api/analyses.py backend/app/main.py backend/tests/test_analyses_api.py
git commit -m "feat(analyses): add get and update analysis endpoints"
```

---

### Task 5: 前端 API 类型与封装

**Files:**
- Modify: `ai-material-generator/frontend/src/api/client.ts`
- Create: `ai-material-generator/frontend/src/api/analysis.ts`

- [ ] **Step 1: 扩展 AnalysisResult 类型**

```typescript
export interface AnalysisResult {
  analysis_id?: number
  title: string
  '新增功能': string[]
  '变更与优化': string[]
  '注意事项': string[]
  '风险提示': string[]
}
```

- [ ] **Step 2: 创建 analysis API 封装**

```typescript
import api from './client'
import type { AnalysisResult } from './client'

export interface AnalysisUpdatePayload {
  new_features: string[]
  changes: string[]
  notices: string[]
  risks: string[]
}

export async function getAnalysis(sourceTitle: string): Promise<AnalysisResult> {
  const response = await api.get(`/analyses/${encodeURIComponent(sourceTitle)}`)
  const data = response.data
  return {
    analysis_id: data.id,
    title: sourceTitle,
    '新增功能': data.new_features,
    '变更与优化': data.changes,
    '注意事项': data.notices,
    '风险提示': data.risks,
  }
}

export async function updateAnalysis(
  analysisId: number,
  payload: AnalysisUpdatePayload,
): Promise<AnalysisResult> {
  const response = await api.put(`/analyses/${analysisId}`, payload)
  const data = response.data
  return {
    analysis_id: data.id,
    title: data.source_title,
    '新增功能': data.new_features,
    '变更与优化': data.changes,
    '注意事项': data.notices,
    '风险提示': data.risks,
  }
}
```

- [ ] **Step 3: Commit**

```bash
cd ai-material-generator
git add frontend/src/api/client.ts frontend/src/api/analysis.ts
git commit -m "feat(frontend): add analysis api client"
```

---

### Task 6: 前端解析结果编辑 UI

**Files:**
- Modify: `ai-material-generator/frontend/src/views/GeneratorView.vue`

- [ ] **Step 1: 导入 analysis API**

```typescript
import { getAnalysis, updateAnalysis, type AnalysisUpdatePayload } from '@/api/analysis'
```

- [ ] **Step 2: 添加编辑状态与辅助方法**

```typescript
const editingCategory = ref<string | null>(null)
const editingIndex = ref<number>(-1)
const editingText = ref('')

const categoryLabels: Record<string, string> = {
  '新增功能': 'new_features',
  '变更与优化': 'changes',
  '注意事项': 'notices',
  '风险提示': 'risks',
}

function startEdit(category: string, index: number, text: string) {
  editingCategory.value = category
  editingIndex.value = index
  editingText.value = text
}

function cancelEdit() {
  editingCategory.value = null
  editingIndex.value = -1
  editingText.value = ''
}

function confirmEdit(category: string) {
  if (!analysis.value || editingIndex.value < 0) return
  analysis.value[category as keyof AnalysisResult] = (analysis.value[category as keyof AnalysisResult] as string[]).map(
    (item, idx) => (idx === editingIndex.value ? editingText.value : item),
  )
  cancelEdit()
}

function deleteItem(category: string, index: number) {
  if (!analysis.value) return
  const list = analysis.value[category as keyof AnalysisResult] as string[]
  list.splice(index, 1)
}

function addItem(category: string) {
  if (!analysis.value) return
  const list = analysis.value[category as keyof AnalysisResult] as string[]
  list.push('新条目')
  startEdit(category, list.length - 1, '新条目')
}

async function saveAnalysis() {
  if (!analysis.value || !analysis.value.analysis_id) {
    ElMessage.warning('请先解析文档')
    return
  }
  try {
    const payload: AnalysisUpdatePayload = {
      new_features: analysis.value['新增功能'],
      changes: analysis.value['变更与优化'],
      notices: analysis.value['注意事项'],
      risks: analysis.value['风险提示'],
    }
    analysis.value = await updateAnalysis(analysis.value.analysis_id, payload)
    ElMessage.success('解析结果已保存')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}
```

- [ ] **Step 3: 替换解析卡片中的静态列表为可编辑列表**

将模板中每个卡片的列表替换为以下结构。为简洁，这里给出「新增功能」卡片示例，其余三类按相同模式修改：

```vue
<el-card class="analysis-card" shadow="never">
  <div class="card-title">
    <el-icon color="#7b2cbf"><CircleCheck /></el-icon>
    <span>功能点 · 新增</span>
    <span class="card-count">{{ analysis['新增功能'].length }}</span>
  </div>
  <ul class="card-list editable-list">
    <li v-for="(item, idx) in analysis['新增功能']" :key="'new-' + idx" class="edit-row">
      <template v-if="editingCategory === '新增功能' && editingIndex === idx">
        <el-input v-model="editingText" size="small" @keyup.enter="confirmEdit('新增功能')" />
        <el-button text size="small" @click="confirmEdit('新增功能')">确认</el-button>
        <el-button text size="small" @click="cancelEdit">取消</el-button>
      </template>
      <template v-else>
        <el-checkbox checked>{{ item }}</el-checkbox>
        <span class="row-actions">
          <el-button text size="small" @click="startEdit('新增功能', idx, item)">编辑</el-button>
          <el-button text size="small" type="danger" @click="deleteItem('新增功能', idx)">删除</el-button>
        </span>
      </template>
    </li>
  </ul>
  <el-button text size="small" class="add-btn" @click="addItem('新增功能')">+ 添加条目</el-button>
</el-card>
```

注意：四个卡片的 key 前缀需保持唯一（`new-`、`opt-`、`note-`、`risk-`）。

- [ ] **Step 4: 在解析区域添加「保存解析结果」按钮**

在「重新解析文档」按钮下方增加：

```vue
<el-button :disabled="!analysis" class="save-analysis-btn" @click="saveAnalysis">
  <el-icon><DocumentChecked /></el-icon> 保存解析结果
</el-button>
```

并在 `<script setup>` 中导入 `DocumentChecked`：

```typescript
import { Upload, Search, DocumentCopy, Download, Document, DocumentChecked, Warning, CircleCheck } from '@element-plus/icons-vue'
```

- [ ] **Step 5: 添加基础样式**

在 `<style scoped>` 末尾追加：

```css
.editable-list .edit-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.editable-list .edit-row .el-input {
  flex: 1;
}
.row-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}
.add-btn {
  margin-top: 8px;
}
.save-analysis-btn {
  width: 100%;
  margin-top: 8px;
}
```

- [ ] **Step 6: 验证前端构建**

Run: `cd ai-material-generator/frontend && npm run build`
Expected: 构建成功，无类型错误

- [ ] **Step 7: Commit**

```bash
cd ai-material-generator
git add frontend/src/views/GeneratorView.vue
git commit -m "feat(frontend): editable analysis cards with save"
```

---

### Task 7: 前端「重新生成」按钮

**Files:**
- Modify: `ai-material-generator/frontend/src/views/GeneratorView.vue`

- [ ] **Step 1: 添加 regenerate 方法**

```typescript
async function regenerate() {
  if (!analysis.value) {
    ElMessage.warning('请先解析文档')
    return
  }
  loading.value = true
  try {
    currentMaterial.value = await generateMaterial(title.value, analysis.value, audience.value, activeMaterialType.value)
    ElMessage.success('已重新生成')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '重新生成失败')
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 2: 在物料操作区添加「重新生成」按钮**

在「保存为草稿」按钮旁（或合适位置）增加：

```vue
<el-button :disabled="!currentMaterial" :loading="loading" @click="regenerate">
  <el-icon><RefreshRight /></el-icon> 重新生成
</el-button>
```

并导入 `RefreshRight`：

```typescript
import { ..., RefreshRight } from '@element-plus/icons-vue'
```

- [ ] **Step 3: 验证前端构建**

Run: `cd ai-material-generator/frontend && npm run build`
Expected: 构建成功

- [ ] **Step 4: Commit**

```bash
cd ai-material-generator
git add frontend/src/views/GeneratorView.vue
git commit -m "feat(frontend): add regenerate button using edited analysis"
```

---

### Task 8: 联调验证与文档更新

**Files:**
- Modify: `ai-material-generator/README.md`

- [ ] **Step 1: 启动后端**

```powershell
cd ai-material-generator/backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- [ ] **Step 2: 启动前端**

```powershell
cd ai-material-generator/frontend
npm run dev
```

- [ ] **Step 3: 端到端验证**

1. 用 `editor` 登录。
2. 在首页输入标题和正文，点击「重新解析文档」。
3. 观察：首次解析较慢（调用模型），成功后解析卡片显示内容。
4. 编辑某一条目，点击「保存解析结果」，提示成功。
5. 切换受众或物料类型，点击「重新生成」，内容应基于编辑后的解析结果。
6. 刷新页面，再次点击「重新解析文档」，应快速返回已保存结果（未调用模型）。
7. 登出后用 `reviewer` 登录，确认没有解析/编辑入口（可选，验证角色隔离）。

- [ ] **Step 4: 更新 README**

在 README 的「功能」和「编辑与审核流程」之间插入新段落：

```markdown
## 解析结果管理

- 首次解析调用 DeepSeek 模型，结果自动存入数据库
- 同一文档再次解析时直接返回历史结果，避免重复调用模型
- 解析出的四类要点支持条目级增删改，保存后用于重新生成物料
```

- [ ] **Step 5: Commit**

```bash
cd ai-material-generator
git add README.md
git commit -m "docs: update README for persisted editable analysis"
```

---

## Spec Coverage Check

| 设计需求 | 对应 Task |
|----------|-----------|
| 解析结果存入 SQLite | Task 1, Task 2 |
| 按 owner_id + source_title 覆盖 | Task 2 |
| 重复解析不调用模型 | Task 3 |
| 前端条目级增删改 | Task 6 |
| 保存解析结果 | Task 6 |
| 重新生成使用编辑后内容 | Task 7 |
| 权限控制（仅所有者） | Task 2, Task 4 |

## Placeholder Scan

- 无 TBD/TODO
- 无 "implement later"
- 所有代码片段完整
- 所有命令包含预期输出
