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
- 海报配图：海报脚本可一键提炼画面描述并生成配图（星语文生图），图片仅本人可见，支持预览/下载/删除

## 技术栈

- 后端：Python 3.11、FastAPI、SQLAlchemy 2.0 async、aiosqlite、python-docx、httpx、requests、passlib、python-jose、星语/Xingyu 或 DeepSeek API
- 前端：Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router + Axios + marked

## 启动

### 后端

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
# 编辑 .env，默认使用星语 API；如需切回 DeepSeek，设置 LLM_PROVIDER=deepseek 并填入 DEEPSEEK_API_KEY
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

1. 首次解析调用大模型（星语 / DeepSeek），结果自动存入数据库。
2. 同一文档再次解析时直接返回历史结果，避免重复调用模型。
3. 解析出的四类要点支持条目级增删改，保存后用于重新生成物料。

## 生成物料缓存与编辑

1. 解析接口立即返回；系统随后在后台为当前受众预热生成全部 6 种物料，每种物料完成即写入数据库缓存。
2. 生成的物料内容按 `source_title + audience + material_type + analysis_hash` 自动存入数据库，`analysis_hash` 由四类要点内容计算得出。
3. 切换受众、物料类型时，若解析结果未改动且预热已完成则直接返回历史结果；预热未完成时会复用同一在飞生成任务，不会重复调用大模型。
4. 在左侧修改解析结果并保存后，再次生成同一组合会基于新解析结果重新调用模型。
5. 当前物料可点击「编辑」进入 Markdown 编辑模式，保存后更新缓存，后续同一解析内容生成时直接返回编辑后的内容。
6. 6 种物料通过 `asyncio.gather` 并发生成，较串行生成显著降低首次生成等待时间。

## 编辑与审核流程

1. editor 登录后生成物料，点击「保存为草稿」。
2. 在「我的资产」页面编辑内容，确认后点击「提交审核」。
3. reviewer 登录后进入「审核」页面，对资产进行「通过」或「驳回」。
4. 已通过资产在「已审核」页面可下载 Markdown。
5. 已 approved 资产被再次编辑后状态自动回落为 draft，需重新审核。

内置账号：

- editor / editor123
- reviewer / reviewer123

## 海报配图

1. 切换到「海报脚本」物料后，内容区底部出现「海报配图」区块。
2. 点击「生成海报图」：画面描述默认填入海报脚本原文，可在弹窗中编辑后生成（后端保留 AI 提炼接口 `/api/posters/prompt`，按 owner+脚本内容哈希缓存，前端入口已暂时下线）。
3. 通过星语文生图生成 PNG（约 15 秒/张），服务端下载转存到 `backend/poster_images/{owner_id}/`，不使用 24 小时过期的 OSS 临时链接。
4. 图片不进审核流程，仅生成者本人可见，支持预览、下载、删除；每次生成产出新图，可多次生成挑选。
5. 相关接口集中在 `/api/posters`（见 `backend/app/api/router.py` 总览）。

## 测试

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests -v

cd ../frontend
npm run build
```

## 环境变量

```env
# 默认使用星语 API；设置为 deepseek 时需提供以下 Key
LLM_PROVIDER=xingyu

# 仅当 LLM_PROVIDER=deepseek 时必填
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```
