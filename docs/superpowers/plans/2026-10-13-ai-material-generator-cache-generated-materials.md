# 生成物料缓存实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将生成的物料内容按 `owner_id + source_title + audience + material_type` 持久化到后端 SQLite，后续相同组合调用 `/generate` 或 `/generate-all` 时直接返回历史结果，避免重复调用 DeepSeek 大模型。

**Architecture:** 新增独立的 `GeneratedMaterial` 缓存表，与 `MaterialAsset` 审核资产表解耦；`/generate` 与 `/generate-all` 在调用模型前先查缓存，命中即返回；生成接口的入参/出参与现有前端调用保持一致。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + aiosqlite / Vue 3 + TypeScript + Element Plus

---

### Task 1: GeneratedMaterial 模型

**Files:**
- Create: `ai-material-generator/backend/app/models/generated_material.py`

- [ ] **Step 1: 创建模型**

```python
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GeneratedMaterial(Base):
    __tablename__ = "generated_materials"
    __table_args__ = (
        UniqueConstraint("owner_id", "source_title", "audience", "material_type", name="uix_generated_material"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    audience: Mapped[str] = mapped_column(String(64), nullable=False)
    material_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "source_title": self.source_title,
            "audience": self.audience,
            "material_type": self.material_type,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
```

- [ ] **Step 2: 验证导入**

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -c "from app.models.generated_material import GeneratedMaterial; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 3: Commit**

```bash
cd ai-material-generator
git add backend/app/models/generated_material.py
git commit -m "feat(generated-material): add GeneratedMaterial cache model"
```

---

### Task 2: 生成物料缓存服务层

**Files:**
- Create: `ai-material-generator/backend/app/services/generated_material_service.py`
- Create: `ai-material-generator/backend/tests/test_generated_material_service.py`

- [ ] **Step 1: 写 upsert 测试（先失败）**

```python
import pytest
from app.services import generated_material_service as svc


@pytest.mark.asyncio
async def test_upsert_creates(db_session):
    gm = await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", content="# 标题\n正文",
    )
    assert gm.id is not None
    assert gm.content == "# 标题\n正文"


@pytest.mark.asyncio
async def test_get_by_composite_key(db_session):
    await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", content="old",
    )
    found = await svc.get_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement",
    )
    assert found is not None
    assert found.content == "old"
```

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_generated_material_service.py::test_upsert_creates -v`
Expected: FAIL `module 'app.services' has no attribute 'generated_material_service'`

- [ ] **Step 2: 实现服务层**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.generated_material import GeneratedMaterial


async def get_generated_material(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    audience: str,
    material_type: str,
) -> GeneratedMaterial | None:
    stmt = select(GeneratedMaterial).where(
        GeneratedMaterial.owner_id == owner_id,
        GeneratedMaterial.source_title == source_title,
        GeneratedMaterial.audience == audience,
        GeneratedMaterial.material_type == material_type,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_generated_material(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    audience: str,
    material_type: str,
    content: str,
) -> GeneratedMaterial:
    gm = await get_generated_material(session, owner_id, source_title, audience, material_type)
    if gm is None:
        gm = GeneratedMaterial(
            owner_id=owner_id,
            source_title=source_title,
            audience=audience,
            material_type=material_type,
        )
        session.add(gm)
    gm.content = content
    await session.commit()
    await session.refresh(gm)
    return gm
```

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_generated_material_service.py -v`
Expected: PASS

- [ ] **Step 3: 写覆盖测试**

```python
@pytest.mark.asyncio
async def test_upsert_overwrites(db_session):
    await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", content="old",
    )
    gm = await svc.upsert_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement", content="new",
    )
    assert gm.content == "new"
    found = await svc.get_generated_material(
        db_session, owner_id=1, source_title="版本说明", audience="网点管理员",
        material_type="version_announcement",
    )
    assert found.content == "new"
```

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_generated_material_service.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd ai-material-generator
git add backend/app/services/generated_material_service.py backend/tests/test_generated_material_service.py
git commit -m "feat(generated-material): add cache service with upsert"
```

---

### Task 3: /generate 接口接入缓存

**Files:**
- Modify: `ai-material-generator/backend/app/api/generator.py`

- [ ] **Step 1: 修改 generate_endpoint 增加缓存逻辑**

在文件顶部导入新增服务：

```python
from app.services import generated_material_service as gm_svc
```

修改 `generate_endpoint`：

```python
@router.post("/generate")
async def generate_endpoint(
    payload: dict,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "editor":
        raise HTTPException(status_code=403, detail="需要 editor 角色")
    title = payload.get("title", "")
    analysis = payload.get("analysis", {})
    audience = payload.get("audience", "")
    material_type = payload.get("material_type", "")
    if not analysis or not audience or not material_type:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    try:
        cached = await gm_svc.get_generated_material(
            db, user.id, title, audience, material_type
        )
        if cached is not None:
            return {**cached.to_dict(), "cached": True}

        result = await generate_material(title, analysis, audience, material_type)
        await gm_svc.upsert_generated_material(
            db, user.id, title, audience, material_type, result["content"]
        )
        return {**result, "cached": False}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成失败: {exc}") from exc
```

- [ ] **Step 2: 写集成测试验证缓存**

创建 `ai-material-generator/backend/tests/test_generate_cache.py`：

```python
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_generate_caches_result(client, editor_token):
    with patch("app.api.generator.generate_material", return_value={
        "title": "R",
        "content": "C",
        "audience": "网点管理员",
        "material_type": "version_announcement",
        "meta": {"audience": "网点管理员", "material_type": "版本宣发稿", "generator": "DeepSeek"},
    }) as mock_generate:
        r = await client.post(
            "/api/generate",
            json={
                "title": "T",
                "analysis": {"新增功能": ["A"]},
                "audience": "网点管理员",
                "material_type": "version_announcement",
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    assert r.status_code == 200
    assert r.json()["content"] == "C"
    assert r.json()["cached"] is False
    mock_generate.assert_called_once()


@pytest.mark.asyncio
async def test_generate_uses_cache(client, editor_token):
    with patch("app.api.generator.generate_material", return_value={
        "title": "R",
        "content": "C",
        "audience": "网点管理员",
        "material_type": "version_announcement",
        "meta": {"audience": "网点管理员", "material_type": "版本宣发稿", "generator": "DeepSeek"},
    }) as mock_generate:
        await client.post(
            "/api/generate",
            json={
                "title": "T",
                "analysis": {"新增功能": ["A"]},
                "audience": "网点管理员",
                "material_type": "version_announcement",
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        r = await client.post(
            "/api/generate",
            json={
                "title": "T",
                "analysis": {"新增功能": ["A"]},
                "audience": "网点管理员",
                "material_type": "version_announcement",
            },
            headers={"Authorization": f"Bearer {editor_token}"},
        )
    assert r.status_code == 200
    assert r.json()["content"] == "C"
    assert r.json()["cached"] is True
    mock_generate.assert_called_once()
```

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_generate_cache.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd ai-material-generator
git add backend/app/api/generator.py backend/tests/test_generate_cache.py
git commit -m "feat(generate): cache generated material and skip model on cache hit"
```

---

### Task 4: /generate-all 接口接入缓存

**Files:**
- Modify: `ai-material-generator/backend/app/api/generator.py`
- Modify: `ai-material-generator/backend/app/services/material_writer.py`（可选，用于支持按需生成）

- [ ] **Step 1: 重构 generate_all_materials 支持按需生成**

修改 `material_writer.py` 中的 `generate_all_materials`，增加 `skip_types` 参数：

```python
async def generate_all_materials(
    title: str, analysis: dict, audience: str, skip_types: set[str] | None = None
) -> list[dict]:
    skip_types = skip_types or set()
    materials = []
    for material_type in MATERIAL_TYPES:
        if material_type in skip_types:
            continue
        materials.append(await generate_material(title, analysis, audience, material_type))
    return materials
```

- [ ] **Step 2: 修改 generate_all_endpoint 增加缓存逻辑**

```python
@router.post("/generate-all")
async def generate_all_endpoint(
    payload: dict,
    user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "editor":
        raise HTTPException(status_code=403, detail="需要 editor 角色")
    title = payload.get("title", "")
    analysis = payload.get("analysis", {})
    audience = payload.get("audience", "")
    if not analysis or not audience:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    try:
        cached_materials = {}
        missing_types = set()
        for material_type in MATERIAL_TYPES:
            cached = await gm_svc.get_generated_material(
                db, user.id, title, audience, material_type
            )
            if cached is not None:
                cached_materials[material_type] = {
                    "title": title,
                    "content": cached.content,
                    "audience": audience,
                    "material_type": material_type,
                    "meta": {
                        "audience": audience,
                        "material_type": MATERIAL_TYPES[material_type],
                        "generator": "DeepSeek",
                    },
                    "cached": True,
                }
            else:
                missing_types.add(material_type)

        generated = await generate_all_materials(title, analysis, audience, missing_types)
        for item in generated:
            await gm_svc.upsert_generated_material(
                db, user.id, title, audience, item["material_type"], item["content"]
            )
            item["cached"] = False

        # 按 MATERIAL_TYPES 顺序合并结果
        materials = []
        for material_type in MATERIAL_TYPES:
            if material_type in cached_materials:
                materials.append(cached_materials[material_type])
            else:
                for item in generated:
                    if item["material_type"] == material_type:
                        materials.append(item)
                        break

        return {"audience": audience, "materials": materials}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成失败: {exc}") from exc
```

注意：需要在文件顶部导入 `MATERIAL_TYPES`：

```python
from app.services.material_writer import generate_material, generate_all_materials, MATERIAL_TYPES
```

- [ ] **Step 3: 写集成测试**

在 `tests/test_generate_cache.py` 中追加：

```python
@pytest.mark.asyncio
async def test_generate_all_caches_and_reuses(client, editor_token):
    with patch("app.api.generator.generate_material", side_effect=lambda title, analysis, audience, mt: {
        "title": f"R-{mt}",
        "content": f"C-{mt}",
        "audience": audience,
        "material_type": mt,
        "meta": {"audience": audience, "material_type": mt, "generator": "DeepSeek"},
    }) as mock_generate:
        r = await client.post(
            "/api/generate-all",
            json={"title": "T", "analysis": {"新增功能": ["A"]}, "audience": "网点管理员"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert r.status_code == 200
        first_count = mock_generate.call_count

        r2 = await client.post(
            "/api/generate-all",
            json={"title": "T", "analysis": {"新增功能": ["A"]}, "audience": "网点管理员"},
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert r2.status_code == 200
        assert mock_generate.call_count == first_count
```

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests/test_generate_cache.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd ai-material-generator
git add backend/app/api/generator.py backend/app/services/material_writer.py backend/tests/test_generate_cache.py
git commit -m "feat(generate-all): cache generated materials per type"
```

---

### Task 5: 全量后端测试

**Files:**
- 无需新增文件

- [ ] **Step 1: 运行全部后端测试**

Run: `cd ai-material-generator/backend && .\venv\Scripts\python.exe -m pytest tests -v`
Expected: 全部通过（原有 27 个 + 新增）

- [ ] **Step 2: Commit（如测试通过则无需单独 commit，否则修复后 commit）**

---

### Task 6: 前端缓存提示

**Files:**
- Modify: `ai-material-generator/frontend/src/views/GeneratorView.vue`

- [ ] **Step 1: 在 generate 成功后提示是否命中缓存**

修改 `doGenerate` 方法：

```typescript
async function doGenerate(materialType: string) {
  if (!analysis.value) return
  activeMaterialType.value = materialType
  loading.value = true
  try {
    currentMaterial.value = await generateMaterial(title.value, analysis.value, audience.value, materialType)
    if ((currentMaterial.value as any).cached) {
      ElMessage.success('已使用历史生成结果')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    loading.value = false
  }
}
```

注意：`Material` 接口目前没有 `cached` 字段。为保持简单，可先用 `(currentMaterial.value as any).cached` 访问。

- [ ] **Step 2: 验证前端构建**

Run: `cd ai-material-generator/frontend && npm run build`
Expected: 构建成功

- [ ] **Step 3: Commit**

```bash
cd ai-material-generator
git add frontend/src/views/GeneratorView.vue
git commit -m "feat(frontend): show cache hit hint for generated material"
```

---

### Task 7: 联调验证与文档更新

**Files:**
- Modify: `ai-material-generator/README.md`
- Create: `ai-material-generator/backend/e2e_generated_smoke.py`

- [ ] **Step 1: 更新 README**

在「解析结果管理」段落之后增加：

```markdown
## 生成物料缓存

- 生成的物料内容按 `source_title + audience + material_type` 自动缓存
- 切换受众、物料类型或重新生成时，相同组合直接返回历史结果，不重复调用大模型
```

- [ ] **Step 2: 创建 E2E 验证脚本**

```python
import httpx

BASE = "http://127.0.0.1:8001"


def login(username: str, password: str) -> str:
    r = httpx.post(f"{BASE}/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["access_token"]


def main():
    token = login("editor", "editor123")
    analysis = {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}

    # 首次生成
    r = httpx.post(
        f"{BASE}/api/generate",
        json={"title": "T", "analysis": analysis, "audience": "网点管理员", "material_type": "version_announcement"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["cached"] is False
    print("first generate ok")

    # 再次生成，应命中缓存
    r2 = httpx.post(
        f"{BASE}/api/generate",
        json={"title": "T", "analysis": analysis, "audience": "网点管理员", "material_type": "version_announcement"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["cached"] is True
    print("cached generate ok")

    print("E2E generated material smoke test passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 启动后端并运行 E2E**

```powershell
cd ai-material-generator/backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

另开终端：

```powershell
cd ai-material-generator/backend
.\venv\Scripts\python.exe e2e_generated_smoke.py
```

Expected: `E2E generated material smoke test passed`

- [ ] **Step 4: Commit**

```bash
cd ai-material-generator
git add README.md backend/e2e_generated_smoke.py
git commit -m "docs: update README and add generated material e2e smoke"
```

---

## Spec Coverage Check

| 设计需求 | 对应 Task |
|----------|-----------|
| 生成物料按组合持久化 | Task 1, Task 2 |
| /generate 命中缓存不调用模型 | Task 3 |
| /generate-all 命中缓存不调用模型 | Task 4 |
| 覆盖式保存 | Task 2 |
| 生成接口需 editor 角色 | Task 3, Task 4 |
| 前端缓存提示 | Task 6 |

## Placeholder Scan

- 无 TBD/TODO
- 无 "implement later"
- 所有代码片段完整
- 所有命令包含预期输出
