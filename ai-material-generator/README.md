# AI 运营物料智能生成助手

输入版本迭代文档（纯文本或 .docx），AI 自动解析出功能点、变更优化、注意事项、风险提示四类要点，并一键生成面向不同受众的六类运营物料初稿。

## 功能

- 左侧输入文档：支持文本粘贴或 .docx 文件上传
- AI 解析结果：四类要点卡片展示
- 物料生成：支持 6 种物料类型 × 3 种受众
  - 版本宣发稿
  - 网点操作指引
  - FAQ 问答库
  - 行者推送话术
  - 海报脚本
  - 培训课件大纲
- 一键复制、下载单页、导出全部 Markdown
- 解析结果管理：首次解析结果自动存入数据库，同文档再次解析直接返回历史结果；四类要点支持条目级增删改，保存后用于重新生成物料
- 编辑与审核工作流：生成后可保存为草稿，编辑后提交审核，reviewer 通过/驳回，仅 approved 资产可下载

## 技术栈

- 后端：Python 3.11、FastAPI、SQLAlchemy 2.0 async、aiosqlite、python-docx、httpx、passlib、python-jose、DeepSeek API
- 前端：Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router + Axios + marked

## 启动

### 后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173/

## 解析结果管理

1. 首次解析调用 DeepSeek 模型，结果自动存入数据库。
2. 同一文档再次解析时直接返回历史结果，避免重复调用模型。
3. 解析出的四类要点支持条目级增删改，保存后用于重新生成物料。

## 生成物料缓存与编辑

1. 首次解析文档时，系统会按当前受众一并生成全部 6 种物料并自动存入数据库。
2. 生成的物料内容按 `source_title + audience + material_type + analysis_hash` 自动存入数据库，`analysis_hash` 由四类要点内容计算得出。
3. 切换受众、物料类型时，若解析结果未改动则直接返回历史结果，不再调用大模型。
4. 在左侧修改解析结果并保存后，再次生成同一组合会基于新解析结果重新调用模型。
5. 当前物料可点击「编辑」进入 Markdown 编辑模式，保存后更新缓存，后续同一解析内容生成时直接返回编辑后的内容。

## 编辑与审核流程

1. editor 登录后生成物料，点击「保存为草稿」。
2. 在「我的资产」页面编辑内容，确认后点击「提交审核」。
3. reviewer 登录后进入「审核」页面，对资产进行「通过」或「驳回」。
4. 已通过资产在「已审核」页面可下载 Markdown。
5. 已 approved 资产被再次编辑后状态自动回落为 draft，需重新审核。

内置账号：

- editor / editor123
- reviewer / reviewer123

## 测试

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests -v

cd ../frontend
npm run build
```

## 环境变量

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```
