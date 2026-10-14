# 释文 DocRelease · 发布文档自动生成系统 设计文档

- 日期：2026-10-14
- 状态：已评审通过（待实施）
- 来源：`demo-app.html`（交互演示，单文件无依赖）
- 目标子项目目录：`doc-release/`

## 1. 背景与目标

`demo-app.html` 演示了一个「发布文档自动生成」产品的完整交互：输入一次发布的代码变更，经 5 步流水线（代码提交合并 → CI 构建成功 → AST 解析变更结构 → LLM 业务化语义改写 → 产物生成并归档），产出三类交付物——功能点清单（CSV）、产品文档（Markdown）、溯源文件（JSON）。

本项目把该演示做成**真实可运行的全栈系统**：

1. **变更输入真实**：真实读取本地 git 仓库（内置示例仓库 + 用户注册的任意仓库），真实解析分支/标签与 diff；
2. **解析真实**：用 tree-sitter 对变更文件做符号级 AST 解析，产出结构化变更集；
3. **生成真实**：调用内部星语大模型，把技术变更改写为面向运营/客服/数据的业务文档语言；
4. **产物真实**：后端确定性渲染器产出三类产物，落库并归档到 `archive/docs/release/<version>/`；
5. **体验保留**：前端复刻 demo 的三栏工作台与实时流水线体验，全部由真实接口与 SSE 驱动。

### 项目位置

新子项目 `doc-release/`，与工作区其他子项目平级、完全独立（不复用其他子项目代码，但沿用其技术栈约定与踩坑经验）。

## 2. 已确认的决策

| 决策点 | 结论 |
| --- | --- |
| 项目形态 | 全栈真实系统：FastAPI 后端 + Vue 3 前端 |
| 数据来源 | 内置示例 git 仓库（开箱可演示）+ 支持注册任意本地 git 仓库 |
| LLM 服务 | 内部星语大模型网关（沿用工作区既有接入经验），可配置回退 DeepSeek |
| 前端范围 | 标准版：三栏工作台 + 发布历史页；术语表用内置配置文件，不做管理界面 |
| 解析深度 | tree-sitter 真实 AST（预编译语言包，Windows + Python 3.11 已验证 wheel 可用） |
| 进度推送 | SSE 实时推送（步骤状态、终端日志、进度、完成事件） |
| 产物生成 | LLM 输出结构化 JSON（业务/技术双写），后端确定性渲染器生成三类产物 |

## 3. 非目标（明确不做）

- 登录认证、多用户与权限体系（全部接口单用户开放）
- 配置中心 UI（术语表、脱敏规则、模型参数均走配置文件与 `.env`）
- 真实 CI 系统接入（Webhook/GitLab/Jenkins API 等）；demo 中「CI 构建成功触发」改为本工具「手动触发运行」
- 前端单元测试框架（与工作区其他子项目一致，以 `npm run build` + 手动冒烟为门槛）
- ts / tsx / go / python 之外语言的符号级解析（未知语言降级为文件级信号）
- 产物在线编辑（本工具产物只读）

## 4. 总体架构

### 4.1 目录结构

```
doc-release/
├── backend/                              # FastAPI + SQLAlchemy 2.0 Async + SQLite
│   ├── app/
│   │   ├── main.py                       # 应用装配、lifespan（建表+示例仓库自检）、CORS、日志中间件
│   │   ├── config.py                     # pydantic-settings，显式 env_file=".env"
│   │   ├── database.py                   # async engine / session / Base
│   │   ├── models/                       # Repo / Run / Artifact
│   │   ├── schemas/                      # Pydantic 请求/响应/SSE 事件/变更集
│   │   ├── api/                          # repos.py / runs.py / artifacts.py / meta.py
│   │   ├── services/
│   │   │   ├── git_service.py            # git CLI 封装：refs、range、diff
│   │   │   ├── parser_service.py         # tree-sitter 符号解析与契约信号
│   │   │   ├── llm_service.py            # provider 路由、分块并发、JSON 修复链
│   │   │   ├── xingyu_api.py             # 星语网关同步封装（asyncio.to_thread）
│   │   │   ├── pipeline_service.py       # 5 步流水线编排、状态机、事件广播
│   │   │   ├── renderers.py              # 三类产物确定性渲染
│   │   │   └── archive_service.py        # 归档目录写入与清理
│   │   ├── prompts/                      # 业务化改写提示词模板（docrelease/v1）
│   │   └── glossary.json                 # 内置企业术语表
│   ├── tests/                            # pytest 测试套件（全异步）
│   ├── seed_sample_repo.py               # 生成示例 git 仓库（order-center 真实历史）
│   ├── sample_repo/order-center/         # 示例仓库落盘位置（种子脚本生成，gitignore）
│   ├── archive/                          # 产物归档目录（docs/release/<version>/，gitignore）
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   └── README.md
└── frontend/                             # Vue 3 + TS + Vite + Pinia + Element Plus
    ├── src/
    │   ├── api/                          # client.ts（axios）、sse.ts（fetch 流解析）
    │   ├── stores/                       # repoStore / runStore
    │   ├── router/                       # / 工作台、/history 历史
    │   ├── views/                        # ConsoleView / HistoryView / HistoryDetailView
    │   ├── components/                   # 见 6.2 组件清单
    │   └── styles/                       # theme.css（复刻 demo 设计语言）
    ├── vite.config.ts                    # @ alias + /api 代理到 127.0.0.1:8000
    ├── package.json / tsconfig*.json / index.html / env.d.ts
    └── README.md
```

仓库根 `README.md` 增加一个子项目小节（doc-release）。

### 4.2 核心数据流

1. 顶部控制条选择「仓库 + 变更范围（base..head）+ 版本标签」→ 左侧面板调 `GET /api/repos/{id}/preview` 展示真实 git diff；
2. 点「运行发布」→ `POST /api/runs` 立即返回 `run_id`，后端 asyncio 后台任务开始执行 5 步流水线；
3. 前端通过 `GET /api/runs/{id}/events`（SSE）订阅 → 中间面板实时更新步骤状态、终端日志、进度条；
4. 运行完成 → `done` 事件携带结构化结果 → 右侧面板用结构化数据**本地渲染**三类产物（术语风格/脱敏开关即时切换不重跑）；「导出当前」走后端渲染下载接口，与归档文件同源一致；
5. `/history` 页列出历次 Run，可回溯任意一次运行的产物、日志与导出。

### 4.3 与 demo 的差异说明

| demo 元素 | 真实系统 | 原因 |
| --- | --- | --- |
| CI 构建成功触发（webhook #2891） | 手动触发运行（记为 `trigger.mode="manual"`） | 不接入真实 CI；本工具定位为发布前预览/补录 |
| 场景为内置静态数据 | 场景 = 示例仓库真实 git 范围（patch/feature/major） | 数据来源决策 |
| trace.json 中 `ciRun` 字段 | `trigger: {mode, runId}` | 去掉虚构的 CI 运行号 |
| 终端日志为预置文案 | git/tree-sitter/星语真实执行日志 | 真实系统 |
| 「跳过动画」按钮 | 保留：跳过前端动画节奏，但不改变后端执行 | 交互一致性 |
| 产物全部前端渲染 | 预览前端渲染 + 导出/归档走后端渲染器 | 归档与导出一致性 |

### 4.4 端口与运行方式

- 后端：`uvicorn app.main:app --reload`（默认 8000；被占用时可用 8001，前端代理与冒烟脚本同步调整）
- 前端：`npm run dev`（5173，`/api` 代理到 127.0.0.1:8000）
- Python 3.11+ / Node.js 22+；SQLite 库文件 `backend/docrelease.db`

## 5. 后端设计

### 5.1 技术栈与依赖

- FastAPI + uvicorn[standard] + pydantic-settings
- SQLAlchemy 2.0 Async + aiosqlite
- tree-sitter + tree-sitter-language-pack（锁定版本，Windows 预编译 wheel 已验证：`tree_sitter-0.26.0-cp311-win_amd64`、`tree_sitter_language_pack-1.22.1-cp310-abi3-win_amd64`）
- requests（星语网关是同步 HTTP 实现）
- pytest + pytest-asyncio + httpx（测试）

### 5.2 配置（config.py / .env.example）

`Settings` 必须显式声明 `env_file=".env"`（工作区已验证的坑：pydantic-settings v2 不声明则不加载 .env），并做存在性判断 `env_file=".env" if Path(".env").exists() else None`。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `xingyu_url` | `http://10.130.13.74:8060/api/chat/chat` | 星语网关地址（内网） |
| `robot_code` | `ROBOT_00000149` | 星语机器人编码 |
| `llm_provider` | `xingyu` | `xingyu`（默认）/ `deepseek`（回退） |
| `deepseek_api_key` | 空 | 可选，回退用；为空时 deepseek 分支直接报错 |
| `llm_timeout` | `120` | 星语单次调用超时（秒） |
| `llm_max_concurrency` | `3` | 分块并发上限 |
| `db_url` | `sqlite+aiosqlite:///./docrelease.db` | SQLite |
| `archive_dir` | `archive` | 归档根目录（相对 backend 工作目录） |
| `sample_repo_dir` | `sample_repo/order-center` | 示例仓库路径 |
| `cors_origins` | `http://localhost:5173,http://127.0.0.1:5173` | 开发期 CORS |

### 5.3 数据模型（SQLAlchemy 异步 ORM，三张表）

**`repos`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK 自增 | |
| name | str | 展示名（默认取目录名） |
| path | str | 绝对路径 |
| is_sample | bool | 是否内置示例仓库 |
| created_at | datetime | |

**`runs`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str(36) PK | uuid4 |
| repo_id | int FK → repos.id | |
| base_ref / head_ref | str | 用户选择的范围端点 |
| version_label | str | 版本标签（如 v2.13.4） |
| tone | str | `business` / `tech`（默认 business） |
| mask | bool | 是否脱敏（默认 false） |
| status | str | `pending` / `running` / `succeeded` / `degraded` / `failed` / `cancelled` |
| current_step | int | 0–4，-1 未开始 |
| steps | JSON | `[{index, name, status(pending/active/done/failed), started_at, finished_at, duration_ms, detail}]` |
| logs | JSON | `[{ts, channel, tag, message}]`，运行中流式发射、结束时整体落库 |
| stats | JSON | `{commits, files, modules, added, removed, days}` |
| result | JSON | 见 5.9 结构化结果契约 |
| error | str nullable | 失败原因（中文） |
| created_at / finished_at | datetime | |

Run 状态机：`pending → running → succeeded | degraded | failed | cancelled`；`degraded` 表示部分 LLM 分块降级但产物可用。

**`artifacts`**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK 自增 | |
| run_id | str(36) FK → runs.id | |
| kind | str | `checklist` / `document` / `trace` |
| filename | str | `checklist.csv` / `product-doc.md` / `trace.json` |
| path | str | 归档绝对路径 |
| bytes | int | 真实文件大小 |
| created_at | datetime | |

模型间不定义 SQLAlchemy `relationship`（工作区经验：避免 mapper 配置期的字符串类名解析问题），只保留外键字段。

### 5.4 API 契约（统一 `/api` 前缀，错误响应统一 `{"detail": "<中文消息>"}`）

| 端点 | 方法 | 说明与关键行为 |
| --- | --- | --- |
| `/health` | GET | `{"status": "ok"}` |
| `/repos` | GET | 仓库列表 `[{id, name, path, is_sample, created_at}]`（示例仓自动登记） |
| `/repos` | POST | 注册本地仓库 `{path, name?}`：路径存在、是 git 仓库（`rev-parse --git-dir` 成功）、未重复注册；否则 400/409 |
| `/repos/{id}` | DELETE | 删除注册记录；**存在历史 runs 时 400 拒绝**（保护审计）；示例仓删除后重启会自动重新登记 |
| `/repos/{id}/refs` | GET | `{branches: [{name, short}], tags: [{name, short}], default_branch}` |
| `/repos/{id}/scenarios` | GET | 示例仓返回 3 个预设场景 `[{id, name, short, version, base, head, description}]`（patch/feature/major）；其他仓返回 `[]` |
| `/repos/{id}/preview?base=&head=` | GET | 变更预览：`{stats, commits: [...], files: [{status, path, added, removed, truncated, lines: [{t, s}]}]}`；ref 无效 422、范围为空 422 |
| `/runs` | POST | `{repo_id, base_ref, head_ref, version_label?, tone?, mask?}` → 201 返回 RunDetail（pending），后台启动流水线；同仓库同范围进行中 ≤1 个，重复 409 |
| `/runs?limit=&offset=` | GET | 历史分页 `{total, items: [RunSummary]}` |
| `/runs/{id}` | GET | RunDetail：含 steps / logs / stats / result / artifacts 摘要 |
| `/runs/{id}/events` | GET | SSE 事件流（5.5） |
| `/runs/{id}/cancel` | POST | 设协作式取消标志；非运行中 409 |
| `/runs/{id}/artifacts/{kind}` | GET | 按 `?tone=&mask=` 渲染产物文本 `{kind, filename, content, tone, mask}`；未完成 409 |
| `/runs/{id}/artifacts/{kind}/download` | GET | 文件下载（attachment），文件名与 demo 导出一致：`功能点清单_<v>.csv` / `业务化产品文档_<v>.md` / `trace_<v>.json` |
| `/runs/{id}` | DELETE | 204；删 artifacts 记录；归档目录仅当其 `trace.json` 的 `trigger.runId` 等于被删 run 时才删（同版本被后续运行覆盖时不误删） |

`version_label` 缺省规则：head 是标签 → 用标签名；否则 `unreleased-<short hash>`。

### 5.5 SSE 协议

`GET /api/runs/{id}/events`，`text/event-stream`。事件表：

| event | data | 时机 |
| --- | --- | --- |
| `snapshot` | `{run: RunDetail}` | 连接/重连立即补发全量当前状态（含已产生 steps/logs/result） |
| `step` | `{index, name, status, duration_ms?, detail?}` | 每步 开始(active) / 结束(done\|failed) |
| `log` | `{channel, tag, message}` | 每行终端日志（channel 对应 demo 的着色通道 s/b/v/t/a/g/r） |
| `progress` | `{percent}` | 步骤切换时（完成步数/5×100） |
| `done` | `{status, result}` | 结束（succeeded/degraded/failed/cancelled），最后一条 |
| `error` | `{message, step_index?}` | 致命错误（随后必有 done） |
| `: ping` 注释行 | — | 15s 心跳防代理超时 |

- 运行已结束时订阅：只发 snapshot + done 即关闭；
- 广播实现：进程内 `RunEventBus`（`run_id → set[asyncio.Queue]`），pipeline 每产生事件向所有订阅队列投递；SSE 端点读自己的队列；订阅/退订影响内存字典，无跨进程需求；
- 前端断线重连采用指数退避，重连后以 snapshot 全量对齐，不依赖历史事件补发。

### 5.6 流水线五步（真实化映射）

五步的展示名（前端面板展示，与 demo 的第 3–5 步完全一致，第 1–2 步按真实语义改写）：① 定位仓库与变更范围；② 收集变更（diff 与统计）；③ AST 解析变更结构；④ LLM 业务化语义改写；⑤ 产物生成并归档。步骤展开区的「读/写/失败」文案为前端静态配置，后端 `detail` 只存运行时真实细节。

1. **`resolve` 定位仓库与变更范围**（毫秒级）——`git rev-parse` 校验并解析 base/head、拉取 commit 列表、计算 stats（commits/files/days）；日志：`detect range <base>..<head> · N commits · M files`
2. **`collect` 收集变更**（毫秒级）——`--name-status` + `--numstat` + 逐文件 `-U3` diff（限额见 5.7）；模块聚类（路径前两级目录）；产出内存态 ChangeSet
3. **`parse` AST 解析变更结构**（秒级）——tree-sitter 逐文件符号对比 + 契约信号（5.8）；不支持语言降级文件级；每条契约信号发 `⚠` 日志
4. **`rewrite` LLM 业务化改写**（星语单次 6–15s，分块并发整体约 10–40s）——分块 → 并发 → JSON 修复 → 合并（5.9）；日志含 glossary 命中、逐块耗时、生成条数、置信度、低置信项
5. **`archive` 产物生成并归档**（毫秒级）——渲染三类产物（5.10）→ 写归档目录 → Artifact 落库；日志含文件名与真实字节数

状态流转：每步开始发 `step(active)` + `progress`，结束发 `step(done/failed)`；任一步失败 → 该步 failed、其余未执行步骤保持 pending、run failed、发 `error` + `done`；取消标志在每步开始与 LLM 分块间检查，命中则 run cancelled（当前步之后未执行步骤保持 pending）。

### 5.7 git 服务行为规范

- 一律 `subprocess` 列表参数调用 git CLI（无 shell），`encoding="utf-8", errors="replace"`，`timeout=60`；超时/非零退出 → `GitError(中文消息)`
- 只读操作：`rev-parse` / `log` / `diff` / `for-each-ref` / `show` / `symbolic-ref`；文件内容一律 `git show <ref>:<path>` 读取，不依赖工作区 checkout 状态
- diff 限额：preview 单文件展示 ≤300 行、流水线内部 ≤400 行，超出截断并 `truncated: true`；二进制文件（`--numstat` 显示 `-`）跳过
- 注入防护：ref 不允许以 `-` 开头；路径仅来自 DB 已注册仓库

### 5.8 tree-sitter 解析规范

- 语言映射：`.ts → typescript`、`.tsx → tsx`、`.go → go`、`.py → python`，其余未知（降级）
- 符号提取（base/head 两版各自解析后对比）：
  - TS/TSX：`export function/class/const`、`export interface/type`
  - Go：首字母大写的 `func`（含方法）/`type`/`const`/`var`
  - Python：模块级 `def`/`class`、全大写常量赋值
  - 符号签名 = 声明首行文本规范化（压缩空白）；同名签名变化 → `changed`
- 输出：`symbols: {added: [], removed: [], changed: []}`（name/kind/signature）
- 契约信号（进 highlights 与日志）：① 导出常量字面量值变更（如 `REFUND_WINDOW_DAYS 7 → 15`）；② 导出符号删除（潜在破坏性）；③ 路由/接口模式变更（正则识别 `/v\d`、HTTP 方法+路径、路由注册参数变化）
- 降级：语言未知或解析异常 → 该文件仅保留文件级信号，日志注明「降级为文件级 diff」；单文件异常不中断整体（逐文件 try/except，计降级数）

### 5.9 LLM 协作规范

**provider 路由**：`llm_service` 按 `settings.llm_provider` 分发 `xingyu`（默认）/ `deepseek`（回退）。

**星语封装（`xingyu_api.py`）**：复刻工作区验证过的合法形态——payload 仅 `{"robotCode", "chatMessages": [{role: system}, {role: user}], "requestId": uuid4}`，**不携带 `agent` 等多余字段**（会返回 401 InvalidParameter）；无鉴权头；同步 `requests` 实现，经 `asyncio.to_thread` 包装；`status==0` 时取 `data.contents[0].content`，否则抛异常并记录响应体。

**分块策略**：按模块聚类分块；单块上限 8 个文件或 diff 总行数 600 行，超出再切分；单块 prompt = 系统模板（角色、输出 JSON schema、术语表、规则）+ 用户内容（该块文件清单、关键 diff、符号变化、契约信号）。

**输出 JSON 契约**（顶层）：

```json
{
  "features": [{
    "tag": "新增|变更|影响面|修复|移除", "risk": "高|中|低", "breaking": false,
    "title": "...", "biz": "业务表述", "tech": "技术表述",
    "visible": "用户可见变化", "scope": "影响范围", "acceptance": "验收要点",
    "action": "运营动作", "role": "负责角色", "paths": ["..."]
  }],
  "highlights": ["契约变更提示..."],
  "confidence": 0.93
}
```

**修复链**：响应提取 JSON（code fence → 首个 `{` 到括号配平截取）→ 校验字段完整性（缺失字段补默认值并计低置信）→ 解析失败附带错误重试 1 次（追加「只输出 JSON」指令）→ 仍失败则该块降级。

**降级策略**：单块失败 → 为该块生成一条「待人工确认」占位功能点（tag=影响面，title=`<模块>变更待人工确认`，附文件列表），记入 `result.lowConfidence`，run 转 `degraded`；**全部块失败** → run `failed`。绝不静默丢弃变更。

**并发与合并**：`asyncio.gather` + `Semaphore(llm_max_concurrency)`；合并时按 title 去重、highlights 合并去重、汇总 token/耗时/置信度均值；`glossaryHits` 为对块内文本做术语别名匹配的真实命中数。

### 5.10 渲染器与三类产物格式

`renderers.py` 为**纯函数**：`render_checklist(result, run, opts)`、`render_document(...)`、`render_trace(...)`；`opts={tone, mask}`；不访问网络与数据库（便于单测与导出复用）。

**checklist.csv**：UTF-8 with BOM（`\ufeff`，Excel 兼容）；表头与 demo 一致：`序号,分类,功能点,业务说明,影响范围,风险,代码路径,验收要点,运营动作,负责角色,破坏性变更`；业务说明按 tone 选 biz/tech；路径按 mask 处理后空格连接；末列 是/否。

**product-doc.md**：八章节与 demo 对齐：① 文档信息（版本/基线/触发方式/解析范围/术语风格/脱敏状态表格）；② 本次发布概览（commits/files/功能点数/跨度，含破坏性变更警示句）；③ 业务能力变更明细（逐条：tag、标题、风险、描述(tone)、可见变化、影响范围、代码路径、破坏性提示）；④ 影响范围与兼容性（四行结论：下游系统/历史数据/客户端兼容/回滚影响，措辞随破坏性变更切换）；⑤ 运营侧需同步动作（动作/角色/类型表）；⑥ 验收要点（#/功能点/判定标准表）；⑦ 变更留痕与决策溯源；⑧ 附录·生成说明与能力边界。

**第七章「变更留痕」的真实数据源**（与 demo 的差异）：demo 中为人工填写的讨论稿时间线；真实系统用**该范围的真实 commit 记录**（日期/作者/标题）作为时间线，契约信号与低置信项作为标注（替代 demo 的「与最终实现不一致」标记）。

**trace.json** 字段结构：

```json
{
  "release": {"version", "branch", "commit", "range", "generatedAt", "generator": "docrelease/1.0.0"},
  "trigger": {"mode": "manual", "runId": "..."},
  "source": {"commits", "files", "modules", "linesAdded", "linesRemoved"},
  "pipeline": [{"step", "name", "ok", "ms"}],
  "llm": {"provider": "xingyu", "model": "xingyu:ROBOT_xxx", "prompt": "docrelease/v1",
          "temperature": 0.2, "tokens": {"inputChars", "outputChars"},
          "glossaryHits", "confidence", "lowConfidence": []},
  "output": {"tone", "masked", "tonePolicy": "business-first|keep-symbols"},
  "artifacts": [{"name", "bytes", "kind"}],
  "risk": {"breakingChanges", "sensitiveReplaced"},
  "retention": {"archive": "docs/release/<version>/", "keepVersions": 24, "immutable": true}
}
```

诚实性约定：星语不返回 token 数，按真实字符数记录（`inputChars/outputChars`）而非编造 token；`commit` 为 head 短 hash（mask 时前 4 位 + `***`）；`sensitiveReplaced` 为 mask 时的路径替换数。

### 5.11 脱敏与术语风格策略

- **mask 应用在渲染期而非存储期**：结构化 result 始终保存原始路径；渲染器按 `opts.mask` 处理：路径 `a/b/c/d.ts → ***/***/c/d.ts`（保留最后两段，与 demo maskPath 一致）、commit 前 4 位 + `***`、range → `***`
- **tone**：渲染器按 `opts.tone` 在 biz/tech 间选择展示字段；归档文件用 run 创建时的 tone/mask（记入 trace.output），导出接口的查询参数可覆盖（参数优先）
- 由此保证：预览、导出、归档三条路径内容同源，任意 tone/mask 组合可由同一结构化结果确定性重现

### 5.12 归档策略

- 归档路径：`<archive_dir>/docs/release/<version>/`，固定三个文件 `checklist.csv` / `product-doc.md` / `trace.json`
- 同 version 二次运行：**覆盖**（发布语义：同版本以最新产物为准），trace 的 `trigger.runId` 指向最新运行
- 删除 run：仅当目录内 trace.json 的 `trigger.runId` == 被删 run.id 时删除目录，否则保留（同版本被后续 run 覆盖的场景不误删）
- 归档写入失败：重试 1 次，仍失败 → 该步 failed、run failed（对应 demo「归档失败重试并告警」语义）

### 5.13 示例仓库种子（seed_sample_repo.py）

- 目标目录 `backend/sample_repo/order-center`，**幂等**（已存在 `.git` 直接跳过）；可作为脚本手动执行，lifespan 也会自检调用
- 用 git CLI 生成；通过 `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` 环境变量还原时间线（2026-06 ~ 2026-10）；作者标识用 `-c user.name/-c user.email` 传入，不污染全局 git 配置
- 标签与场景范围：`v2.13.3`（基线）→ `v2.13.4`（补丁场景：`v2.13.3..v2.13.4`）→ `v2.14.0`（功能场景：`v2.13.3..v2.14.0`，含补丁内容）→ `v3.0.0`（大版本场景：`v2.14.0..v3.0.0`）
- 内容按 demo 三个场景真实落地（TS/TSX/Go + package.json/go.mod/README.md 佐料），**基线版先写旧实现、后续提交改为新实现**（保证 diff 与符号对比真实）：
  - 补丁批：`src/report/export/stream.ts`（新增分片）、`retry.ts`（新增）、`index.ts`（改造）、`api/report/export.go`（新增 cursor）
  - 功能批：`src/order/coupon/stack.ts`（pickBestCoupon→resolveBestCombination）、`src/checkout/summary.tsx`、`src/aftersale/policy.ts`（REFUND_WINDOW_DAYS 7→15）、`api/order/list.go`（CouponStackable）、`src/member/benefit/verify.ts`、`src/goods/detail/price.tsx`
  - 大版本批：`api/legacy/order.go`（CreateOrderV1 删除）、`src/order/state/machine.ts`（transition→apply 事件溯源）、`src/inventory/multi-warehouse.ts`（新增）、`src/pay/callback/verify.ts`（md5→hmacSha256）、`src/seckill/stock/deduct.ts`（Lua 原子扣减）、`src/aftersale/partial-refund.ts`（新增）、`src/auth/sms.ts`（loginBySms 删除）
- 提交信息用中文、每个逻辑变更独立提交（保证 commits 统计真实）；种子完成后以 `is_sample=True` 注册 Repo

### 5.14 术语表（glossary.json）

- 结构：`{"version": "1", "terms": [{"term": "分片流式写出", "aliases": ["stream export", "chunked", "分片"], "note": "..."}]}`
- 覆盖 demo 语境术语 20+ 条：分片流式写出、退避重试、券叠加、最优组合、预计到手价、实时校验、事件溯源、多仓协同、部分退款、原子扣减、游标续取、签名升级等
- 用途：① 拼入 LLM system prompt（术语归一指引）；② 命中统计：对块内路径/diff/符号文本做别名匹配，结果计入运行日志与 trace.llm.glossaryHits

## 6. 前端设计

### 6.1 页面与路由

| 路由 | 视图 | 说明 |
| --- | --- | --- |
| `/` | ConsoleView | 三栏工作台（复刻 demo 布局与视觉） |
| `/history` | HistoryView | 发布历史列表（版本/仓库/范围/状态/耗时/操作） |
| `/history/:id` | HistoryDetailView | 历史运行详情：复用 OutputPanel + 步骤/日志回看 + 重新导出/删除 |

顶栏（topbar）与 demo 一致：品牌、当前页导航、右侧链接。

### 6.2 组件清单

| 组件 | 职责 |
| --- | --- |
| ControlBar | 仓库下拉、场景 seg（仅示例仓）、base/head 下拉、版本标签输入、tone seg、mask 开关、运行/跳过按钮、live 状态徽章 |
| DiffPanel | 仓库信息头（分支/范围/变更量/触发）+ 逐文件 diff（scanned/cursor 高亮由 store 驱动） |
| PipelinePanel | StepList + 进度条 + TerminalLog |
| StepList / StepItem | 五步状态列表；展开区的「读/写/失败」文案为静态配置（与 demo 一致） |
| TerminalLog | 日志行渲染（channel 着色、自动滚动） |
| OutputPanel | 三 tab：ChecklistView / DocView / TraceView + 空态 + 导出按钮；数据源为结构化 result |
| RunTable | 历史页列表与操作（查看/导出/删除） |
| StatusBadge | 运行状态徽章（pending/running/succeeded/degraded/failed/cancelled） |

### 6.3 状态管理（Pinia）

- `repoStore`：repos、currentRepoId、refs、scenarios、preview（含 loading/error）
- `runStore`：currentRun（steps/logs/status/result/artifacts）、SSE 句柄、事件归约（applyEvent）、startRun、重连、cancel；历史列表数据由视图局部状态管理
- tone/mask 为控制条选择器状态，创建 run 时传后端；运行结束后切换只影响预览与导出（不重跑）

### 6.4 SSE 客户端（`api/sse.ts`）

- `fetch` + `ReadableStream` + `TextDecoder` 手动解析 `event:`/`data:` 块（完全可控心跳与错误）
- 心跳注释行忽略；指数退避重连（1s/2s/4s/8s，最多 5 次）；重连后以 `snapshot` 全量对齐
- 提供 `subscribe(runId, onEvent) → {close}`；组件卸载时 abort

### 6.5 样式还原策略

- `styles/theme.css` 移植 demo 的 CSS 变量与关键类（topbar/panel/step/term/tabs/table/json/时间线/tag/chip/stat/note-box）
- Element Plus 用于表单类控件（ElSelect/ElInput/ElSwitch/ElMessage）；产物 tabs、面板、终端等用自定义组件以保持还原度
- 响应式断点与 demo 一致（1180/820）

### 6.6 页面行为与后端交互

- 进入页面：加载 repos → 默认选示例仓 → 加载 refs + scenarios → 默认选中 feature 场景 → 加载 preview 填充左栏
- 运行：`POST /runs` → 建立 SSE → 事件驱动三栏（`step` 驱动左栏 scanned 动画与中栏步骤、`log` 驱动终端、`done` 驱动右栏渲染）
- 运行中：禁止切换仓库/场景/重复运行，可取消；刷新页面后先 `GET /runs/{id}` 再重新订阅恢复现场
- 导出：直接访问后端 download URL（带当前 tone/mask 参数）触发浏览器下载

## 7. 错误处理矩阵

| 场景 | 后端行为 | 前端表现 |
| --- | --- | --- |
| 注册非 git 目录/路径不存在 | 400 中文消息 | ElMessage 报错 |
| ref 无效 / 范围为空 | 422 | preview 阶段即提示，不发起运行 |
| git 命令失败/超时 | run failed，error 落库 | 步骤标红、终端红色日志、done(failed) |
| LLM 单块失败 | 重试 1 次 → 降级占位 + lowConfidence | run degraded，产物含「待人工确认」项 |
| LLM 全部块失败 | run failed | 同 git 失败路径 |
| 未支持语言 / 单文件解析异常 | 文件级降级 | 日志注明降级 |
| 归档写入失败 | 重试 1 次后 run failed | 同上 |
| SSE 断线 | — | 指数退避重连 + snapshot 对齐 |
| 取消运行 | 协作式取消，cancelled | done(cancelled) + 状态徽章 |
| run 未完成时导出 | 409 | 导出按钮禁用 |
| 查/删不存在的 run | 404 | 历史页提示 |
| 同仓库同范围重复运行 | 409 | 提示已有运行进行中 |

## 8. 测试策略

**后端 pytest（pytest-asyncio），全量测试不打真实星语（autouse 打桩，保证秒级~分钟级内跑完）**：

- `conftest.py`：tmp_path 真实 git 仓库 fixture（写文件+commit+tag，含 TS/Go 样例）；TestClient（httpx ASGITransport）；autouse monkeypatch LLM（patch 目标为 `llm_service` 内**实际解析**的名字，按 provider 选择，遵循工作区经验）
- `test_git_service`：refs 枚举、range 校验、diff 解析、非法 ref、非 git 目录
- `test_parser_service`：TS/Go/Python 符号提取与对比、三类契约信号、未知语言与异常降级
- `test_llm_service`：JSON 提取（fence/括号配平）、修复重试、分块合并与去重、降级占位、并发 gather
- `test_renderers`：三类产物确定性断言（CSV BOM/表头/行数、MD 八章节、trace 字段；mask 生效、tone 切换）
- `test_pipeline`：小仓库端到端（替身 LLM）→ 状态推进、产物落库、归档文件存在、事件序列（直接订阅 RunEventBus 断言）
- `test_api`：repos（注册/409/删除保护）、refs/scenarios/preview、runs CRUD、cancel、产物渲染与下载、404/409/422 分支

**前端**：`npm run build` 通过为门槛；手动冒烟清单（工作台完整运行、tone/mask 切换、导出三文件、历史回看、错误提示）。不引入前端单测框架（与工作区其他子项目一致）。

**E2E 冒烟 `backend/e2e_smoke.py`（httpx）**：脚本**在进程内**启动 uvicorn（后台线程）并在启动前于进程内打桩 LLM（不向生产代码加 Fake 开关，遵循工作区经验）；流程：确认示例仓 → 拉 refs/scenarios → 逐个场景创建 run → SSE 观测 done → 校验三类产物内容与归档目录一致、bytes 与实际文件大小一致 → 打印 PASS/FAIL。可选 `--real` 参数不打桩，直连真实星语，仅供手动联调。

## 9. 验收标准

1. 后端全量 pytest 通过，且不依赖网络（无真实星语调用）
2. 前端 `npm run build` 通过
3. 示例仓库种子生成成功，三场景可选且 preview 展示真实 diff 与统计
4. 端到端（替身）：任选场景 → SSE 实时推进 5 步 → 三类产物落库并归档 → 导出文件与归档一致
5. 真实星语联调：补丁场景一次成功，产物含业务/技术双表述、影响范围、验收要点、运营动作；trace 记录真实字符数与置信度
6. tone/mask 切换即时生效，导出文件与之匹配
7. 历史页可回看任意 run 的产物与日志；删除 run 时归档清理规则正确生效
8. 非法仓库、非法 refs、重复运行等错误路径均有清晰中文提示
9. 任意本地 git 仓库可注册并真实完成一次流水线（真实星语或降级均可，链路不报错）

## 10. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 星语内网不可达/响应慢 | 全部测试打桩；超时 120s + 重试 + 降级路径；错误信息清晰 |
| tree-sitter API 变动 | 锁定版本（tree-sitter==0.26.0、tree-sitter-language-pack==1.22.1） |
| Windows 路径/编码问题 | subprocess 列表参数 + utf-8/replace；路径统一 Path 处理 |
| 大仓库 diff/上下文过大 | 单文件与单块行数限额、截断标记、分块再切分 |
| LLM 产物质量波动 | JSON 修复链 + 字段校验 + 低置信显式标注（不静默编造） |
| 同版本重复运行覆盖归档 | trace.trigger.runId 绑定 + 删除保护规则 |
| 8000 端口被占用（含幽灵占用） | 支持备用端口 8001；前端代理与冒烟基址可配 |

## 11. 交付物清单

- `doc-release/backend`：完整后端（含 pytest 套件、seed 脚本、e2e 冒烟、.env.example、README）
- `doc-release/frontend`：完整前端（工作台 + 发布历史，`npm run build` 通过）
- 仓库根 `README.md` 增补 doc-release 子项目小节
- 本设计文档（`docs/superpowers/specs/2026-10-14-doc-release-design.md`）及后续实施计划文档

