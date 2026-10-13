# 内容生产发布工作台使用手册

本文档汇总 content-workbench 的核心使用流程与常见注意事项，帮助用户快速上手并理解"一键生成"背后的资料选择机制。

---

## 1. 系统简介

内容生产发布工作台面向内部运营团队，支持：

- 创建内容项目并设定主题、受众、语气
- 粘贴/导入产品文档、操作手册等原始资料
- 一键生成三类资产：公告（announcement）、FAQ（faq）、海报文案（poster）
- 覆盖式编辑、提交审核、审核者审阅、下载 Markdown/HTML、模拟发布
- 完整的操作审计日志

---

## 2. 环境准备

### 2.1 安装依赖

后端：

```powershell
cd content-workbench/backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

前端：

```powershell
cd content-workbench/frontend
npm install
```

### 2.2 配置环境变量

复制示例配置文件并填入 DeepSeek API Key：

```powershell
cd content-workbench/backend
copy .env.example .env
```

编辑 `.env`：

```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LOG_LEVEL=INFO
```

> 注意：pydantic-settings v2 不会自动读取 `.env`，已在 `app/config.py` 中显式声明 `env_file` 加载路径。

---

## 3. 启动服务

### 3.1 生产/真实生成模式

```powershell
cd content-workbench/backend
$env:DATABASE_URL="sqlite+aiosqlite:///./workbench.db"
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 另一个终端
cd content-workbench/frontend
npm run dev
```

访问地址：

- 前端：`http://localhost:5173/`
- 后端 API 文档：`http://127.0.0.1:8000/docs`

### 3.2 测试/演示模式（不调用真实 DeepSeek）

使用专用 E2E 入口，自动注入 `FakeGenerator`：

```powershell
cd content-workbench/backend
$env:DATABASE_URL="sqlite+aiosqlite:///./e2e.db"
.\venv\Scripts\python.exe -m uvicorn app.e2e_main:app --host 127.0.0.1 --port 8000
```

> 如果 `8000` 端口被幽灵占用（`netstat` 显示 LISTENING 但无法连接或 taskkill 找不到进程），请改用 `8001`，并同步在前端 `frontend/.env.local` 中设置 `VITE_API_TARGET=http://127.0.0.1:8001`，然后重启 vite dev server。

---

## 4. 账号与角色

系统内置两个互斥角色：

| 角色 | 用户名 | 密码 | 权限 |
|---|---|---|---|
| 编辑者 | editor | editor123 | 创建项目、添加资料、一键生成、编辑资产、提交审核、下载 approved 资产、模拟发布 |
| 审核者 | reviewer | review123 | 查看待审资产、通过/驳回审核、查看审计日志 |

---

## 5. 完整业务流程

### 5.1 创建项目

1. 使用 `editor` 登录
2. 进入「项目中心」
3. 点击「新建项目」，填写：
   - 项目名称
   - 主题（theme）：生成时用于筛选资料的关键词
   - 受众（audience）：生成时用于筛选资料的关键词
   - 语气（tone）：影响生成文案风格

### 5.2 添加资料

1. 在项目列表点击项目，进入「资料中心」
2. 输入资料名称和正文，点击「添加资料」
3. 可添加多条资料，系统会自动按内容哈希去重
4. 添加完成后，可点击「查看」按钮预览资料原文
5. 点击「进入工作台」跳转至创作工作台

### 5.3 一键生成

在创作工作台点击「一键生成」，系统会：

1. 读取该项目下的全部资料
2. 把资料切分为句子片段
3. 用项目的 theme + audience 作为关键词给片段打分
4. 只保留命中关键词的片段，并按相关度取前 `max_evidence_chunks` 条
5. 把这些片段作为证据交给大模型生成三类资产

> 生成成功后，工作台会显示 announcement、faq、poster 三条 draft 资产。

### 5.4 编辑与提交审核

1. 编辑者可对 draft 资产进行覆盖式编辑
2. 编辑满意后点击「提交审核」，资产状态变为 `pending_review`
3. `pending_review` 状态下禁止再次编辑
4. 一旦 approved 资产被再次编辑，状态会自动回落为 `draft`，需要重新提交审核

### 5.5 审核与发布

1. 使用 `reviewer` 登录
2. 进入「审核与交付」查看待审列表
3. 查看资产内容及引用来源，选择「通过」或「驳回」
4. 审核通过后，编辑者可对 approved 资产进行下载或模拟发布

---

## 6. 多资料生成机制

当用户提交多个资料时，**系统不会只使用某一个资料**，而是：

- 遍历项目下所有资料
- 将每条资料按空行、句号、感叹号、问号切分成片段
- 过滤掉长度小于 5 个字符的片段
- 用项目主题和受众作为关键词，统计每个片段命中关键词的次数
- 保留命中次数大于 0 的片段，按分数从高到低排序
- 取前 `max_evidence_chunks` 条作为最终证据

因此，**资料越多、相关片段越丰富，生成结果的可信度越高**；但如果所有资料都没有命中项目主题或受众关键词，系统会拒答。

---

## 7. 常见错误：提示缺少资料

点击「一键生成」返回 422 时，可能有以下两种情况：

### 7.1 项目下没有任何资料

错误信息：

```
该项目暂无资料，请先添加资料后再生成
```

解决：在资料中心添加至少一条资料。

### 7.2 资料与项目主题/受众不相关或内容过短

错误信息：

```
现有资料与项目主题/受众不相关或内容过短，请补充相关资料
```

触发原因：

- 资料正文没有包含项目的 theme 或 audience 关键词
- 资料片段长度小于 5 个字符，被检索过滤
- 资料内容虽然相关，但使用的措辞与主题/受众关键词不匹配

解决：

- 在资料中明确写出项目主题词和受众词
- 避免只粘贴过短的片段
- 确保资料正文与项目设定高度相关

---

## 8. 快速生成测试数据

### 8.1 一键生成完整演示数据

在测试模式下启动后端后，运行脚本：

```powershell
cd content-workbench/backend
$env:WORKBENCH_API_URL="http://127.0.0.1:8000/api"
.\venv\Scripts\python seed_demo_data.py
```

该脚本会自动完成：创建项目 → 添加资料 → 一键生成 → 提交审核 → 审核通过 → 模拟发布。

### 8.2 API 测试数据示例

`content-workbench/backend/test_data_sample.json` 中提供了可直接用于 Postman 或 curl 的测试数据，包括：

- 可正常生成的项目与资料
- 资料不相关、无资料、资料过短等拒答场景
- 登录、创建项目、添加资料、一键生成的完整请求模板

---

## 9. 测试与验证

### 9.1 后端单元测试

```powershell
cd content-workbench/backend
.\venv\Scripts\python.exe -m pytest tests -v
```

当前基线：45 passed。

### 9.2 前端构建

```powershell
cd content-workbench/frontend
npm run build
```

构建成功会输出 `dist/` 目录。

---

## 10. 注意事项

- 资料按内容哈希去重，重复提交相同内容会返回 409
- 仅 `approved` 状态的资产允许下载和模拟发布
- 无足够证据时系统会拒答并返回 422，不会产生半成品资产
- 所有关键操作（生成、编辑、提交、审核、下载、发布）均记录审计日志
- 开发调试时可使用 `app.e2e_main:app` 入口避免真实 LLM 调用

---

## 11. 相关文档

- 需求设计：`docs/superpowers/specs/2026-10-13-content-generation-workbench-design.md`
- 实施计划：`docs/superpowers/plans/2026-10-13-content-generation-workbench.md`
- E2E 测试设计：`docs/superpowers/specs/2026-10-13-content-workbench-playwright-e2e-design.md`
- 生成拒答诊断：`docs/superpowers/specs/2026-10-13-generate-missing-source-analysis.md`
