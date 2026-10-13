# AI 运营物料智能生成助手 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建独立子项目 `ai-material-generator`，实现「输入版本迭代文档（文本/.docx）→ AI 解析要点 → 一键生成六类运营物料」的完整前后端应用。

**Architecture:** 后端 FastAPI 暴露 `/api/parse` 和 `/api/generate*` 接口，调用 DeepSeek OpenAI 兼容 API 完成文档解析与物料生成；前端 Vue3 + Element Plus 复刻参考截图的左右两栏布局。前后端通过 Axios 交互，文件上传使用 multipart/form-data。

**Tech Stack:** Python 3.11、FastAPI、python-docx、httpx、DeepSeek API；Vue 3、TypeScript、Vite、Element Plus、Axios。

---

## 文件结构

```
ai-material-generator/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── generator.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── docx_parser.py
│   │       ├── analyzer.py
│   │       └── material_writer.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_docx_parser.py
│   │   ├── test_analyzer.py
│   │   ├── test_material_writer.py
│   │   └── test_api.py
│   ├── requirements.txt
│   ├── .env.example
│   └── pytest.ini
└── frontend/
    ├── src/
    │   ├── main.ts
    │   ├── App.vue
    │   ├── api/
    │   │   └── client.ts
    │   ├── views/
    │   │   └── GeneratorView.vue
    │   └── styles/
    │       └── index.css
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    ├── tsconfig.app.json
    ├── tsconfig.node.json
    ├── vite.config.ts
    └── env.d.ts
```

---

### Task 1: 后端项目骨架与配置

**Files:**
- Create: `ai-material-generator/backend/requirements.txt`
- Create: `ai-material-generator/backend/pytest.ini`
- Create: `ai-material-generator/backend/.env.example`
- Create: `ai-material-generator/backend/app/__init__.py`
- Create: `ai-material-generator/backend/app/config.py`
- Create: `ai-material-generator/backend/app/main.py`

- [ ] **Step 1: 创建 requirements.txt**

```text
fastapi==0.141.1
uvicorn==0.52.4
python-docx==1.1.2
httpx==0.28.1
pydantic-settings==2.15.0
pytest==9.1.1
pytest-asyncio==1.3.0
python-multipart==0.0.20
```

- [ ] **Step 2: 创建 pytest.ini**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 3: 创建 .env.example**

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

- [ ] **Step 4: 创建 app/config.py**

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env" if Path(".env").exists() else None,
        env_file_encoding="utf-8",
    )
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"


settings = Settings()
```

- [ ] **Step 5: 创建 app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.generator import router

app = FastAPI(title="AI 运营物料智能生成助手")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 6: 创建空 __init__.py**

```bash
New-Item -ItemType File -Force -Path ai-material-generator/backend/app/__init__.py
New-Item -ItemType File -Force -Path ai-material-generator/backend/app/api/__init__.py
New-Item -ItemType File -Force -Path ai-material-generator/backend/app/services/__init__.py
```

- [ ] **Step 7: 启动后端验证**

```powershell
cd ai-material-generator/backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

访问 `http://127.0.0.1:8000/api/health`，Expected: `{"status":"ok"}`

- [ ] **Step 8: Commit**

```bash
git add ai-material-generator/backend
git commit -m "feat(material-generator): backend skeleton and config"
```

---

### Task 2: docx 解析服务

**Files:**
- Create: `ai-material-generator/backend/app/services/docx_parser.py`
- Create: `ai-material-generator/backend/tests/test_docx_parser.py`

- [ ] **Step 1: 编写测试**

```python
import os
from docx import Document
from app.services.docx_parser import parse_docx_file


def test_parse_docx_file(tmp_path):
    doc = Document()
    doc.add_paragraph("第一段")
    doc.add_paragraph("第二段")
    path = tmp_path / "test.docx"
    doc.save(path)
    assert parse_docx_file(path) == "第一段\n第二段"


def test_parse_empty_docx(tmp_path):
    doc = Document()
    path = tmp_path / "empty.docx"
    doc.save(path)
    assert parse_docx_file(path) == ""
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
cd ai-material-generator/backend
.\venv\Scripts\python.exe -m pytest tests/test_docx_parser.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.docx_parser'`

- [ ] **Step 3: 实现 docx_parser.py**

```python
from pathlib import Path
from docx import Document


def parse_docx_file(path: Path | str) -> str:
    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_docx_parser.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai-material-generator/backend
git commit -m "feat(material-generator): docx parser service"
```

---

### Task 3: AI 解析服务

**Files:**
- Create: `ai-material-generator/backend/app/services/analyzer.py`
- Create: `ai-material-generator/backend/tests/test_analyzer.py`

- [ ] **Step 1: 编写测试（使用 monkeypatch 隔离 LLM）**

```python
import json
import pytest
from app.services.analyzer import analyze_document


@pytest.mark.asyncio
async def test_analyze_document(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return json.dumps({
            "新增功能": ["异常件一键上报"],
            "变更与优化": ["运单批量导入"],
            "注意事项": ["需升级至 V3.2.0"],
            "风险提示": ["数据存在延迟"],
        })

    monkeypatch.setattr("app.services.analyzer._chat", fake_chat)
    result = await analyze_document("网点管家 V3.2.0", "本次新增异常件一键上报功能。")
    assert result["新增功能"] == ["异常件一键上报"]
    assert result["变更与优化"] == ["运单批量导入"]
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_analyzer.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 analyzer.py**

```python
import json
import httpx
from app.config import settings


PARSE_PROMPT = """你是一名资深运营文档分析师。请从下面的版本迭代文档中提取四类信息，并以 JSON 格式返回。
提取要求：
1. 新增功能：列出本次新增的功能点
2. 变更与优化：列出功能改进、流程优化、体验优化等
3. 注意事项：列出用户需要关注或提前准备的事项
4. 风险提示：列出可能出现的问题或风险

每类信息返回字符串数组，每条控制在 30 字以内。如果某类没有内容，返回空数组。

文档标题：{title}
文档正文：
{content}

请只返回 JSON，不要返回任何解释性文字。格式示例：
{{
  "新增功能": ["..."],
  "变更与优化": ["..."],
  "注意事项": ["..."],
  "风险提示": ["..."]
}}"""


async def _chat(messages: list[dict]) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{settings.deepseek_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": settings.deepseek_model,
                "messages": messages,
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def analyze_document(title: str, content: str) -> dict:
    prompt = PARSE_PROMPT.format(title=title, content=content)
    raw = await _chat([{"role": "user", "content": prompt}])
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(raw[start:end + 1])
        else:
            raise ValueError(f"解析结果不是合法 JSON: {raw}") from exc
    for key in ["新增功能", "变更与优化", "注意事项", "风险提示"]:
        if key not in data:
            data[key] = []
    return data
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_analyzer.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai-material-generator/backend
git commit -m "feat(material-generator): AI analyzer service"
```

---

### Task 4: AI 生成服务

**Files:**
- Create: `ai-material-generator/backend/app/services/material_writer.py`
- Create: `ai-material-generator/backend/tests/test_material_writer.py`

- [ ] **Step 1: 编写测试**

```python
import pytest
from app.services.material_writer import generate_material, MATERIAL_TYPES


@pytest.mark.asyncio
async def test_generate_material(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return "# 网点管家 V3.2.0 上线公告\n\n各位网点负责人：..."

    monkeypatch.setattr("app.services.material_writer._chat", fake_chat)
    analysis = {
        "新增功能": ["异常件一键上报"],
        "变更与优化": ["运单批量导入"],
        "注意事项": ["需升级"],
        "风险提示": ["数据延迟"],
    }
    result = await generate_material("网点管家 V3.2.0", analysis, "网点管理员", "version_announcement")
    assert result["title"] == "网点管家 V3.2.0 上线公告"
    assert "各位网点负责人" in result["content"]
    assert result["material_type"] == "version_announcement"
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_material_writer.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 实现 material_writer.py**

```python
import httpx
from app.config import settings


MATERIAL_TYPES = {
    "version_announcement": "版本宣发稿",
    "operation_guide": "网点操作指引",
    "faq": "FAQ 问答库",
    "push_script": "行者推送话术",
    "poster_script": "海报脚本",
    "training_outline": "培训课件大纲",
}

GENERATE_PROMPT = """你是一名资深运营文案。请根据以下版本迭代要点，为「{audience}」受众撰写一篇「{type_name}」。

文档标题：{title}
新增功能：
{新增功能}
变更与优化：
{变更与优化}
注意事项：
{注意事项}
风险提示：
{风险提示}

写作要求：
- 语气专业、清晰、易读
- 突出对受众的实际价值
- 风险提示放在文末
- 返回 Markdown 格式正文，不需要代码块包裹

请直接输出正文。"""


async def _chat(messages: list[dict]) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{settings.deepseek_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": settings.deepseek_model,
                "messages": messages,
                "temperature": 0.5,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def _format_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "无"


def _extract_title(content: str, default: str) -> str:
    for line in content.splitlines():
        line = line.strip().lstrip("# ").lstrip("#")
        if line:
            return line
    return default


async def generate_material(title: str, analysis: dict, audience: str, material_type: str) -> dict:
    if material_type not in MATERIAL_TYPES:
        raise ValueError(f"不支持的物料类型: {material_type}")
    prompt = GENERATE_PROMPT.format(
        title=title,
        audience=audience,
        type_name=MATERIAL_TYPES[material_type],
        新增功能=_format_list(analysis.get("新增功能", [])),
        变更与优化=_format_list(analysis.get("变更与优化", [])),
        注意事项=_format_list(analysis.get("注意事项", [])),
        风险提示=_format_list(analysis.get("风险提示", [])),
    )
    content = await _chat([{"role": "user", "content": prompt}])
    return {
        "title": _extract_title(content, title),
        "content": content,
        "audience": audience,
        "material_type": material_type,
        "meta": {
            "audience": audience,
            "material_type": MATERIAL_TYPES[material_type],
            "generator": "DeepSeek",
        },
    }


async def generate_all_materials(title: str, analysis: dict, audience: str) -> list[dict]:
    materials = []
    for material_type in MATERIAL_TYPES:
        materials.append(await generate_material(title, analysis, audience, material_type))
    return materials
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_material_writer.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ai-material-generator/backend
git commit -m "feat(material-generator): AI material writer service"
```

---

### Task 5: FastAPI 路由

**Files:**
- Create: `ai-material-generator/backend/app/api/generator.py`
- Create: `ai-material-generator/backend/tests/test_api.py`
- Modify: `ai-material-generator/backend/app/main.py`

- [ ] **Step 1: 实现 generator.py**

```python
from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.services.docx_parser import parse_docx_file
from app.services.analyzer import analyze_document
from app.services.material_writer import generate_material, generate_all_materials

router = APIRouter()


@router.post("/parse")
async def parse_endpoint(
    title: str = Form(...),
    content: str = Form(""),
    file: UploadFile | None = File(None),
):
    if not content and not file:
        raise HTTPException(status_code=400, detail="请输入文档正文或上传 .docx 文件")
    if file and not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="仅支持 .docx 格式 Word 文档")
    try:
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
        return {"title": title, **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"文档解析失败: {exc}") from exc


@router.post("/generate")
async def generate_endpoint(payload: dict):
    title = payload.get("title", "")
    analysis = payload.get("analysis", {})
    audience = payload.get("audience", "")
    material_type = payload.get("material_type", "")
    if not analysis or not audience or not material_type:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    try:
        return await generate_material(title, analysis, audience, material_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成失败: {exc}") from exc


@router.post("/generate-all")
async def generate_all_endpoint(payload: dict):
    title = payload.get("title", "")
    analysis = payload.get("analysis", {})
    audience = payload.get("audience", "")
    if not analysis or not audience:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    try:
        materials = await generate_all_materials(title, analysis, audience)
        return {"audience": audience, "materials": materials}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成失败: {exc}") from exc
```

- [ ] **Step 2: 修改 main.py 引入 router**

```python
from app.api.generator import router as generator_router
app.include_router(generator_router, prefix="/api")
```

- [ ] **Step 3: 编写 API 测试（使用 TestClient + monkeypatch）**

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_parse_text(client, monkeypatch):
    async def fake_analyze(*args, **kwargs):
        return {"新增功能": ["A"], "变更与优化": [], "注意事项": [], "风险提示": []}
    monkeypatch.setattr("app.api.generator.analyze_document", fake_analyze)
    response = client.post("/api/parse", data={"title": "T", "content": "C"})
    assert response.status_code == 200
    assert response.json()["新增功能"] == ["A"]


def test_generate(client, monkeypatch):
    async def fake_generate(*args, **kwargs):
        return {"title": "R", "content": "C", "audience": "网点管理员", "material_type": "version_announcement"}
    monkeypatch.setattr("app.api.generator.generate_material", fake_generate)
    response = client.post("/api/generate", json={
        "title": "T",
        "analysis": {"新增功能": ["A"]},
        "audience": "网点管理员",
        "material_type": "version_announcement",
    })
    assert response.status_code == 200
    assert response.json()["title"] == "R"
```

- [ ] **Step 4: 安装 python-multipart 并运行测试**

```powershell
.\venv\Scripts\python.exe -m pip install python-multipart==0.0.20
.\venv\Scripts\python.exe -m pytest tests/test_api.py -v
```

Expected: PASS

- [ ] **Step 5: 启动后端并用 curl/脚本测试真实 API**

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

使用 Postman 或临时脚本测试 `/api/parse` 和 `/api/generate`。

- [ ] **Step 6: Commit**

```bash
git add ai-material-generator/backend
git commit -m "feat(material-generator): FastAPI parse and generate endpoints"
```

---

### Task 6: 前端项目骨架

**Files:**
- Create: `ai-material-generator/frontend/package.json`
- Create: `ai-material-generator/frontend/tsconfig.json`
- Create: `ai-material-generator/frontend/tsconfig.app.json`
- Create: `ai-material-generator/frontend/tsconfig.node.json`
- Create: `ai-material-generator/frontend/vite.config.ts`
- Create: `ai-material-generator/frontend/env.d.ts`
- Create: `ai-material-generator/frontend/index.html`
- Create: `ai-material-generator/frontend/src/main.ts`
- Create: `ai-material-generator/frontend/src/App.vue`
- Create: `ai-material-generator/frontend/src/styles/index.css`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "ai-material-generator-frontend",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.5.13",
    "element-plus": "^2.9.7",
    "@element-plus/icons-vue": "^2.3.1",
    "axios": "^1.8.4",
    "marked": "^15.0.7"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.3",
    "typescript": "~5.7.3",
    "vite": "^6.2.4",
    "vue-tsc": "^2.2.8"
  }
}
```

- [ ] **Step 2: 创建 tsconfig.json**

```json
{
  "files": [],
  "references": [{ "path": "./tsconfig.app.json" }, { "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: 创建 tsconfig.app.json**

```json
{
  "extends": "@vue/tsconfig/tsconfig.dom.json",
  "include": ["env.d.ts", "src/**/*", "src/**/*.vue"],
  "exclude": ["src/**/__tests__/*"],
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

- [ ] **Step 4: 创建 tsconfig.node.json**

```json
{
  "extends": "@tsconfig/node22/tsconfig.json",
  "include": ["vite.config.*"],
  "compilerOptions": {
    "composite": true,
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "module": "ESNext",
    "types": ["node"]
  }
}
```

- [ ] **Step 5: 创建 vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 6: 创建 env.d.ts**

```typescript
/// <reference types="vite/client" />
```

- [ ] **Step 7: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI 运营物料智能生成助手</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 8: 创建 src/main.ts**

```typescript
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import './styles/index.css'

const app = createApp(App)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.use(ElementPlus)
app.mount('#app')
```

- [ ] **Step 9: 创建 src/App.vue**

```vue
<template>
  <GeneratorView />
</template>

<script setup lang="ts">
import GeneratorView from './views/GeneratorView.vue'
</script>
```

- [ ] **Step 10: 创建 src/styles/index.css**

```css
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: #f5f7fa;
  color: #303133;
}
```

- [ ] **Step 11: 安装依赖并验证 build**

```powershell
cd ai-material-generator/frontend
npm install
npm run build
```

Expected: build success

- [ ] **Step 12: Commit**

```bash
git add ai-material-generator/frontend
git commit -m "feat(material-generator): frontend skeleton"
```

---

### Task 7: 前端 API Client

**Files:**
- Create: `ai-material-generator/frontend/src/api/client.ts`

- [ ] **Step 1: 实现 client.ts**

```typescript
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

export interface AnalysisResult {
  title: string
  '新增功能': string[]
  '变更与优化': string[]
  '注意事项': string[]
  '风险提示': string[]
}

export interface Material {
  title: string
  content: string
  audience: string
  material_type: string
  meta: {
    audience: string
    material_type: string
    generator: string
  }
}

export async function parseDocument(title: string, content: string, file?: File): Promise<AnalysisResult> {
  const form = new FormData()
  form.append('title', title)
  if (file) {
    form.append('file', file)
  } else {
    form.append('content', content)
  }
  const response = await api.post('/parse', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function generateMaterial(
  title: string,
  analysis: AnalysisResult,
  audience: string,
  materialType: string,
): Promise<Material> {
  const response = await api.post('/generate', {
    title,
    analysis,
    audience,
    material_type: materialType,
  })
  return response.data
}

export async function generateAllMaterials(
  title: string,
  analysis: AnalysisResult,
  audience: string,
): Promise<{ audience: string; materials: Material[] }> {
  const response = await api.post('/generate-all', {
    title,
    analysis,
    audience,
  })
  return response.data
}

export default api
```

- [ ] **Step 2: Commit**

```bash
git add ai-material-generator/frontend
git commit -m "feat(material-generator): frontend API client"
```

---

### Task 8: 前端 GeneratorView 页面

**Files:**
- Create: `ai-material-generator/frontend/src/views/GeneratorView.vue`

- [ ] **Step 1: 实现 GeneratorView.vue**

页面需要复刻截图布局：左侧输入区、右侧解析结果区和物料生成区。由于代码较长，分两段写入。

先写入 script + 部分 template：

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import type { AnalysisResult, Material } from '../api/client'
import { parseDocument, generateMaterial, generateAllMaterials } from '../api/client'

const title = ref('网点管家 V3.2.0 版本迭代说明')
const content = ref(`【版本】网点管家 V3.2.0\n【发布日期】2026-10-20\n【适用范围】全国加盟网点\n\n一、新增功能\n1. 新增「异常件一键上报」功能\n网点扫描异常件后，可在首页直接发起上报，系统自动带出运单号、异常类型、上报时间，无需手工填写。\n\n二、优化与调整\n1. 运单批量导入：导入失败时返回具体失败原因与失败行号，便于网点自行排错。\n2. 消息中心：重要通知将后台自动推送，先在小部分网点试点，逐步放开至 30% 网点。\n3. 在线客服：由「我的」调整至「首页 - 帮助中心」。\n4. 旧版对账单：统一使用新版对账单。\n\n三、注意事项\n1. 本次版本需网点管家升级至 V3.2.0 以上版本方可使用新功能。\n2. 派费日结数据存在 24 小时延迟，以财务系统最终数据为准。\n3. 升级期间请勿强制关闭 App，避免数据同步异常。\n\n四、风险提示\n如出现派费数据缺失，请勿重复提交申诉，等待系统次日补数即可。遇到问题请勿重复操作，及时联系区域客服。`)
const file = ref<File | null>(null)
const analysis = ref<AnalysisResult | null>(null)
const currentMaterial = ref<Material | null>(null)
const allMaterials = ref<Material[]>([])
const loading = ref(false)
const analysisCollapsed = ref(false)
const audience = ref('网点管理员')
const activeMaterialType = ref('version_announcement')

const audiences = ['网点管理员', '业务员', '内部汇报']
const materialTypes = [
  { key: 'version_announcement', label: '版本宣发稿', num: '01' },
  { key: 'operation_guide', label: '网点操作指引', num: '02' },
  { key: 'faq', label: 'FAQ 问答库', num: '03' },
  { key: 'push_script', label: '行者推送话术', num: '04' },
  { key: 'poster_script', label: '海报脚本', num: '05' },
  { key: 'training_outline', label: '培训课件大纲', num: '06' },
]

const stats = computed(() => {
  const lines = content.value.split('\n').length
  const chars = content.value.length
  return `${chars} 字 · ${lines} 行`
})

function onFileChange(raw: any) {
  const list = raw?.fileList || raw
  if (list && list.length > 0) {
    file.value = list[0].raw || list[0]
  }
}

async function doParse() {
  if (!title.value) {
    ElMessage.warning('请输入文档标题')
    return
  }
  if (!content.value && !file.value) {
    ElMessage.warning('请输入文档正文或上传 .docx 文件')
    return
  }
  loading.value = true
  try {
    analysis.value = await parseDocument(title.value, content.value, file.value || undefined)
    ElMessage.success('解析完成')
    await doGenerate('version_announcement')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '解析失败')
  } finally {
    loading.value = false
  }
}

async function doGenerate(materialType: string) {
  if (!analysis.value) return
  activeMaterialType.value = materialType
  loading.value = true
  try {
    currentMaterial.value = await generateMaterial(title.value, analysis.value, audience.value, materialType)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    loading.value = false
  }
}

async function doGenerateAll() {
  if (!analysis.value) return
  loading.value = true
  try {
    const result = await generateAllMaterials(title.value, analysis.value, audience.value)
    allMaterials.value = result.materials
    ElMessage.success('全部物料已生成')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    loading.value = false
  }
}

function copyContent() {
  if (!currentMaterial.value) return
  navigator.clipboard.writeText(currentMaterial.value.content)
  ElMessage.success('已复制')
}

function downloadCurrent() {
  if (!currentMaterial.value) return
  const blob = new Blob([currentMaterial.value.content], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${currentMaterial.value.title}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function renderMarkdown(md: string) {
  return marked(md)
}
</script>
```

- [ ] **Step 2: 追加 template 部分**

用 SearchReplace 在 `</script>` 后追加以下 template：

```vue
<template>
  <div class="page">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-icon">+</div>
        <div>
          <h1 class="brand-title">AI 运营物料智能生成助手</h1>
          <p class="brand-subtitle">POC 概念验证：输入版本迭代文档，一键产出六类推广物料初稿</p>
        </div>
      </div>

      <div class="step-badge">1</div>
      <h2 class="step-title">输入文档</h2>

      <el-input v-model="title" placeholder="请输入文档标题" class="input-title" />

      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".docx"
        class="uploader"
        @change="onFileChange"
      >
        <el-icon class="upload-icon"><Upload /></el-icon>
        <div class="upload-text">
          <span class="upload-link">点击或拖拽上传文档</span>
          <span>支持 .docx，也可直接粘贴正文</span>
        </div>
        <div v-if="file" class="upload-file">{{ file.name }}</div>
      </el-upload>

      <el-input
        v-model="content"
        type="textarea"
        :rows="16"
        placeholder="粘贴产品文档、版本迭代说明等文本"
        class="content-input"
      />

      <div class="stats">{{ stats }}</div>

      <el-button type="primary" :loading="loading" class="parse-btn" @click="doParse">
        <el-icon><Search /></el-icon>
        重新解析文档
      </el-button>
      <p class="parse-tip">解析结果可逐条勾选，未勾选的内容不会进入物料</p>
    </aside>

    <main class="main">
      <section v-show="!analysisCollapsed" class="section analysis-section">
        <div class="section-header">
          <div class="section-title">
            <span class="step-badge-inline">2</span>
            <span>AI 解析结果</span>
            <span v-if="analysis" class="section-status">解析完成</span>
          </div>
          <el-button text @click="analysisCollapsed = !analysisCollapsed">
            {{ analysisCollapsed ? '展开' : '收缩' }}
          </el-button>
        </div>

        <div v-if="analysis" class="analysis-grid">
          <el-card class="analysis-card" shadow="never">
            <div class="card-title">
              <el-icon color="#7b2cbf"><CircleCheck /></el-icon>
              <span>功能点 · 新增</span>
              <span class="card-count">{{ analysis['新增功能'].length }}</span>
            </div>
            <ul class="card-list">
              <li v-for="(item, idx) in analysis['新增功能']" :key="'new-' + idx">
                <el-checkbox checked>{{ item }}</el-checkbox>
              </li>
            </ul>
          </el-card>

          <el-card class="analysis-card" shadow="never">
            <div class="card-title">
              <el-icon color="#7b2cbf"><CircleCheck /></el-icon>
              <span>变更与优化</span>
              <span class="card-count">{{ analysis['变更与优化'].length }}</span>
            </div>
            <ul class="card-list">
              <li v-for="(item, idx) in analysis['变更与优化']" :key="'opt-' + idx">
                <el-checkbox checked>{{ item }}</el-checkbox>
              </li>
            </ul>
          </el-card>

          <el-card class="analysis-card" shadow="never">
            <div class="card-title">
              <el-icon color="#7b2cbf"><CircleCheck /></el-icon>
              <span>注意事项</span>
              <span class="card-count">{{ analysis['注意事项'].length }}</span>
            </div>
            <ul class="card-list">
              <li v-for="(item, idx) in analysis['注意事项']" :key="'note-' + idx">
                <el-checkbox checked>{{ item }}</el-checkbox>
              </li>
            </ul>
          </el-card>

          <el-card class="analysis-card warning" shadow="never">
            <div class="card-title">
              <el-icon color="#e6a23c"><Warning /></el-icon>
              <span>风险提示</span>
              <span class="card-count">{{ analysis['风险提示'].length }}</span>
            </div>
            <ul class="card-list">
              <li v-for="(item, idx) in analysis['风险提示']" :key="'risk-' + idx">
                <el-checkbox checked>{{ item }}</el-checkbox>
              </li>
            </ul>
          </el-card>
        </div>
      </section>

      <section class="section generate-section">
        <div class="section-header">
          <div class="section-title">
            <span class="step-badge-inline">3</span>
            <span>物料生成</span>
          </div>
        </div>
        <p class="generate-subtitle">切换受众，文案语感自动改写</p>

        <div class="audience-tabs">
          <el-radio-group v-model="audience" size="large" @change="() => doGenerate(activeMaterialType)">
            <el-radio-button v-for="a in audiences" :key="a" :label="a">{{ a }}</el-radio-button>
          </el-radio-group>
        </div>

        <div class="material-tabs">
          <el-check-tag
            v-for="mt in materialTypes"
            :key="mt.key"
            :checked="activeMaterialType === mt.key"
            class="material-tag"
            @change="doGenerate(mt.key)"
          >
            <span class="material-num">{{ mt.num }}</span>
            {{ mt.label }}
          </el-check-tag>
        </div>

        <p class="generate-hint">生成后可直接复制或导出 Markdown</p>

        <div class="material-actions">
          <el-button :disabled="!currentMaterial" @click="copyContent">
            <el-icon><DocumentCopy /></el-icon> 复制
          </el-button>
          <el-button :disabled="!currentMaterial" @click="downloadCurrent">
            <el-icon><Download /></el-icon> 下载本页
          </el-button>
          <el-button type="primary" :loading="loading" :disabled="!analysis" @click="doGenerateAll">
            <el-icon><Document /></el-icon> 导出全部
          </el-button>
        </div>

        <div v-if="currentMaterial" v-loading="loading" class="material-content">
          <h2 class="material-title">{{ currentMaterial.title }}</h2>
          <div class="material-meta">
            <span>受众：{{ currentMaterial.meta.audience }}</span>
            <span class="meta-sep">|</span>
            <span>物料类型：{{ currentMaterial.meta.material_type }}</span>
            <span class="meta-sep">|</span>
            <span>生成方式：{{ currentMaterial.meta.generator }}</span>
          </div>
          <div class="markdown-body" v-html="renderMarkdown(currentMaterial.content)" />
        </div>

        <el-empty v-else description="点击「重新解析文档」生成物料" />
      </section>
    </main>
  </div>
</template>

<style scoped>
.page { display: flex; min-height: 100vh; background: #f8f9fc; }
.sidebar { width: 380px; flex-shrink: 0; background: #fff; padding: 24px; border-right: 1px solid #ebeef5; }
.brand { display: flex; gap: 12px; margin-bottom: 24px; }
.brand-icon { width: 40px; height: 40px; background: #7b2cbf; color: #fff; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 24px; }
.brand-title { margin: 0; font-size: 18px; color: #303133; }
.brand-subtitle { margin: 4px 0 0; font-size: 12px; color: #909399; }
.step-badge { width: 28px; height: 28px; background: #7b2cbf; color: #fff; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; margin-bottom: 8px; }
.step-title { margin: 0 0 16px; font-size: 16px; }
.input-title { margin-bottom: 12px; }
.uploader { margin-bottom: 12px; }
.uploader :deep(.el-upload-dragger) { width: 100%; padding: 24px; }
.upload-icon { font-size: 32px; color: #7b2cbf; margin-bottom: 8px; }
.upload-text { display: flex; flex-direction: column; font-size: 13px; color: #606266; }
.upload-link { color: #7b2cbf; font-weight: 500; }
.upload-file { margin-top: 8px; color: #7b2cbf; font-size: 12px; }
.content-input { margin-bottom: 8px; }
.stats { text-align: right; font-size: 12px; color: #909399; margin-bottom: 12px; }
.parse-btn { width: 100%; margin-bottom: 8px; }
.parse-tip { font-size: 12px; color: #909399; text-align: center; margin: 0; }
.main { flex: 1; padding: 24px; overflow-y: auto; }
.section { background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,.04); }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.section-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; }
.step-badge-inline { width: 24px; height: 24px; background: #7b2cbf; color: #fff; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }
.section-status { font-size: 12px; color: #67c23a; font-weight: normal; }
.analysis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.analysis-card :deep(.el-card__body) { padding: 16px; }
.card-title { display: flex; align-items: center; gap: 8px; font-weight: 600; margin-bottom: 12px; }
.card-count { margin-left: auto; background: #f4e9ff; color: #7b2cbf; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.card-list { list-style: none; padding: 0; margin: 0; }
.card-list li { margin: 6px 0; font-size: 13px; }
.generate-subtitle { color: #909399; font-size: 13px; margin: -8px 0 16px; }
.audience-tabs { margin-bottom: 16px; }
.material-tabs { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.material-tag { padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.material-tag.is-checked { background: #7b2cbf; color: #fff; }
.material-num { margin-right: 6px; opacity: .7; }
.generate-hint { color: #909399; font-size: 12px; margin: 0 0 12px; }
.material-actions { display: flex; gap: 10px; margin-bottom: 20px; }
.material-content { border: 1px solid #ebeef5; border-radius: 8px; padding: 24px; background: #fff; }
.material-title { margin: 0 0 12px; color: #7b2cbf; font-size: 22px; }
.material-meta { color: #606266; font-size: 13px; margin-bottom: 16px; padding: 12px; background: #fdf6ec; border-left: 4px solid #e6a23c; }
.meta-sep { margin: 0 8px; color: #c0c4cc; }
.markdown-body { line-height: 1.8; }
.markdown-body :deep(h3) { color: #303133; margin-top: 20px; }
.markdown-body :deep(ul) { padding-left: 20px; }
.markdown-body :deep(li) { margin: 6px 0; }
</style>
```

- [ ] **Step 3: 运行前端 build**

```powershell
cd ai-material-generator/frontend
npm run build
```

Expected: build success

- [ ] **Step 4: Commit**

```bash
git add ai-material-generator/frontend
git commit -m "feat(material-generator): GeneratorView UI"
```

---

### Task 9: 前后端联调与 README

**Files:**
- Create: `ai-material-generator/README.md`
- Modify: `ai-material-generator/frontend/vite.config.ts`（如有端口变化）

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

- [ ] **Step 3: 浏览器验证**

1. 访问 `http://localhost:5173/`
2. 点击「重新解析文档」，确认右侧出现解析结果卡片
3. 切换受众和物料类型，确认内容变化
4. 点击「导出全部」，确认六类物料生成
5. 上传一个 .docx 文件，确认能解析并生成

- [ ] **Step 4: 创建 README.md**

```markdown
# AI 运营物料智能生成助手

输入版本迭代文档（文本或 .docx），AI 自动解析要点并一键生成六类运营物料初稿。

## 启动

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd ../frontend
npm install
npm run dev
```

访问 http://localhost:5173/

## 测试

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests -v

cd ../frontend
npm run build
```
```

- [ ] **Step 5: 全量测试**

```powershell
cd ai-material-generator/backend
.\venv\Scripts\python.exe -m pytest tests -v
```

Expected: all tests pass

```powershell
cd ai-material-generator/frontend
npm run build
```

Expected: build success

- [ ] **Step 6: Commit**

```bash
git add ai-material-generator
git commit -m "feat(material-generator): integration and README"
```

---

## Spec Coverage Check

| 设计文档要求 | 对应 Task |
|---|---|
| 后端 FastAPI 骨架 | Task 1 |
| .env 加载配置 | Task 1 |
| docx 解析 | Task 2 |
| AI 解析要点 | Task 3 |
| AI 生成物料 | Task 4 |
| /api/parse /api/generate /api/generate-all | Task 5 |
| 后端测试 | Task 2-5 |
| Vue3 + Vite + Element Plus 前端骨架 | Task 6 |
| Axios API client | Task 7 |
| 复刻截图布局的 GeneratorView | Task 8 |
| 前后端联调 + README | Task 9 |

## Placeholder Scan

- 无 TBD/TODO
- 所有代码步骤均提供完整代码
- 所有测试命令和预期输出明确

## Type Consistency Check

- `AnalysisResult` 字段与后端返回一致：`title`、`新增功能`、`变更与优化`、`注意事项`、`风险提示`
- `Material` 字段与后端返回一致：`title`、`content`、`audience`、`material_type`、`meta`
- `material_type` 枚举前后端一致：version_announcement、operation_guide、faq、push_script、poster_script、training_outline
