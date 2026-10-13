# AI 运营物料智能生成助手 · 设计文档

> 复刻参考链接：https://www.workbuddy.link/p/Cgex10VA6liauj3zTt5j7D?source=2

## 目标

构建一个独立的 Web 应用，用户输入版本迭代文档（纯文本或 .docx），AI 自动解析出功能点、变更优化、注意事项、风险提示四类要点，并基于解析结果一键生成面向不同受众的六类运营物料初稿。

## 技术栈

- 后端：Python 3.11、FastAPI、python-docx、httpx
- 前端：Vue 3 + TypeScript + Vite + Element Plus + Axios
- LLM：DeepSeek OpenAI 兼容 API

## 项目结构

```
ai-practice/ai-material-generator/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 应用入口
│   │   ├── config.py            # 配置与 .env 加载
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── generator.py     # /api/parse /api/generate /api/generate-all
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── docx_parser.py   # .docx 解析
│   │       ├── analyzer.py      # DeepSeek 解析要点
│   │       └── material_writer.py # DeepSeek 生成物料
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_parse.py
│   │   └── test_generate.py
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

## 后端 API 设计

### 1. 解析文档

```http
POST /api/parse
Content-Type: multipart/form-data
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| title | string | 是 | 文档标题 |
| content | string | 否 | 正文，与 file 二选一 |
| file | file | 否 | .docx 文件，与 content 二选一 |

响应：

```json
{
  "title": "网点管家 V3.2.0 版本迭代说明",
  "新增功能": ["异常件一键上报", "派费日结"],
  "变更与优化": ["运单批量导入", "消息中心", "在线客服", "旧版对账单"],
  "注意事项": [
    "本次版本需网点管家升级至 V3.2.0 以上版本方可使用新功能",
    "派费日结数据存在 24 小时延迟，以财务系统最终数据为准",
    "升级期间请勿强制关闭 App，避免数据同步异常"
  ],
  "风险提示": ["如出现派费数据缺失，请勿重复提交申诉，等待系统次日补数即可"]
}
```

### 2. 生成单类物料

```http
POST /api/generate
Content-Type: application/json
```

请求体：

```json
{
  "title": "网点管家 V3.2.0 版本迭代说明",
  "analysis": {
    "新增功能": ["异常件一键上报", "派费日结"],
    "变更与优化": ["运单批量导入", "消息中心", "在线客服", "旧版对账单"],
    "注意事项": ["..."],
    "风险提示": ["..."]
  },
  "audience": "网点管理员",
  "material_type": "version_announcement"
}
```

响应：

```json
{
  "title": "网点管家 V3.2.0 上线公告",
  "content": "# 网点管家 V3.2.0 上线公告\n\n各位网点负责人：\n...",
  "audience": "网点管理员",
  "material_type": "version_announcement",
  "meta": {
    "audience": "网点管理员",
    "material_type": "版本宣发稿",
    "generator": "DeepSeek"
  }
}
```

### 3. 批量生成全部物料

```http
POST /api/generate-all
Content-Type: application/json
```

请求体：同 `/api/generate`，不含 `material_type`。

响应：

```json
{
  "audience": "网点管理员",
  "materials": [
    {"material_type": "version_announcement", "title": "...", "content": "..."},
    {"material_type": "operation_guide", "title": "...", "content": "..."},
    {"material_type": "faq", "title": "...", "content": "..."},
    {"material_type": "push_script", "title": "...", "content": "..."},
    {"material_type": "poster_script", "title": "...", "content": "..."},
    {"material_type": "training_outline", "title": "...", "content": "..."}
  ]
}
```

### 4. 健康检查

```http
GET /api/health
```

响应：`{"status": "ok"}`

## 物料类型定义

| 标识 | 名称 | 输出形式 |
|---|---|---|
| version_announcement | 版本宣发稿 | Markdown 文章 |
| operation_guide | 网点操作指引 | Markdown 分步骤指南 |
| faq | FAQ 问答库 | Markdown 问答列表 |
| push_script | 行者推送话术 | Markdown 短文案 |
| poster_script | 海报脚本 | Markdown 文案 + 卖点 |
| training_outline | 培训课件大纲 | Markdown 大纲 |

## 受众定义

- 网点管理员
- 业务员
- 内部汇报

## Prompt 设计

### 解析 Prompt

```text
你是一名资深运营文档分析师。请从下面的版本迭代文档中提取四类信息，并以 JSON 格式返回。
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
{
  "新增功能": ["..."],
  "变更与优化": ["..."],
  "注意事项": ["..."],
  "风险提示": ["..."]
}
```

### 生成 Prompt

```text
你是一名资深运营文案。请根据以下版本迭代要点，为「{audience}」受众撰写一篇「{material_type_name}」。

文档标题：{title}
新增功能：
{新增功能列表}
变更与优化：
{变更与优化列表}
注意事项：
{注意事项列表}
风险提示：
{风险提示列表}

写作要求：
- 语气专业、清晰、易读
- 突出对受众的实际价值
- 风险提示放在文末
- 返回 Markdown 格式正文，不需要代码块包裹

请直接输出正文。
```

## 前端页面设计

### 布局

整体左右两栏：

- 左侧：固定 380px 宽，包含输入区
- 右侧：自适应宽度，包含解析结果区和物料生成区

### 左侧输入区

从上到下：

1. 页面标题：`AI 运营物料智能生成助手`
2. 副标题：`POC 概念验证：输入版本迭代文档，一键产出六类推广物料初稿`
3. 步骤 1：输入文档
   - 文档标题输入框（placeholder：请输入文档标题）
   - 文件上传区：虚线边框，提示「点击或拖拽上传文档，支持 .docx，也可直接粘贴正文」
   - 正文文本域：多行输入
   - 字数/行数统计
   - 「重新解析文档」按钮（primary）

### 右侧解析结果区

1. 步骤 2：AI 解析结果
   - 右上角「收缩/展开」按钮
   - 2x2 网格卡片：
     - 新增功能（紫色图标 + 数量角标）
     - 变更与优化（紫色图标 + 数量角标）
     - 注意事项（紫色图标 + 数量角标）
     - 风险提示（橙色图标 + 数量角标）
   - 每张卡片内展示要点列表，每条前带勾选图标

### 右侧物料生成区

1. 步骤 3：物料生成
   - 副标题：`切换受众，文案语感自动改写`
   - 受众切换标签：网点管理员 / 业务员 / 内部汇报
   - 物料类型标签：01 版本宣发稿 / 02 网点操作指引 / 03 FAQ 问答库 / 04 行者推送话术 / 05 海报脚本 / 06 培训课件大纲
   - 提示文案：`生成后可直接复制或导出 Markdown`
   - 操作按钮：复制、下载本页、导出全部
   - 内容展示区：
     - 标题（大字号）
     - 元信息条：受众 | 物料类型 | 生成方式
     - Markdown 渲染正文

## 数据流

1. 用户在左侧输入标题和正文，或上传 .docx
2. 点击「重新解析文档」→ 前端发送 `POST /api/parse`
3. 后端解析 .docx（如有）→ 拼接正文 → 调用 DeepSeek 解析 → 返回四类要点
4. 前端展示解析结果卡片
5. 用户选择受众和物料类型 → 前端发送 `POST /api/generate`
6. 后端调用 DeepSeek 生成对应物料 → 返回 Markdown 内容
7. 前端渲染内容，支持复制、下载单页、导出全部

## 错误处理

| 场景 | 处理方式 |
|---|---|
| 未提供正文且未上传文件 | 返回 400，提示「请输入文档正文或上传 .docx 文件」 |
| 上传非 docx 文件 | 返回 400，提示「仅支持 .docx 格式 Word 文档」 |
| docx 解析失败 | 返回 422，提示「文档解析失败，请检查文件内容」 |
| DeepSeek API Key 缺失 | 启动时报错，API 返回 503，提示「未配置 LLM API Key」 |
| DeepSeek 调用失败 | 返回 502，提示「AI 服务暂时不可用，请稍后重试」 |
| 解析结果非合法 JSON | 返回 502，记录原始响应供调试 |

## 测试策略

- 后端单元测试：
  - docx 解析测试
  - 解析 API 测试（mock LLM 返回固定 JSON）
  - 生成 API 测试（mock LLM 返回固定 Markdown）
  - 参数校验测试
- 前端构建验证：`npm run build` 通过
- 端到端冒烟：上传 docx → 解析 → 切换受众 → 生成全部六类物料

## 部署与运行

### 后端

```powershell
cd ai-material-generator/backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 前端

```powershell
cd ai-material-generator/frontend
npm install
npm run dev
```

### 环境变量

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

## 与现有项目的关系

本项目为独立子项目，不依赖 content-workbench 或 content-ops-agent。后续可考虑复用其 Element Plus 主题或接入其审核流程。
