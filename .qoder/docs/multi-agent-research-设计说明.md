# multi-agent-research 设计说明

## 1. 功能定位

输入一个调研主题，系统把主题拆解为若干子问题，人工确认大纲后依次完成**检索 → 分析 → 写作 → 核查**，产出带引用编号的 Markdown 调研报告。

核心目标不是检索效果，而是把**多 Agent 编排**的工程要素完整落地：

- 编排器与角色解耦：编排器只管状态与顺序，角色只管单次输入输出。
- 结构化中间态：每个角色的输出先落库（步骤、子问题、证据），再进入下一环节。
- 唯一可恢复暂停点：Planner 完成后停在 `awaiting_outline`，用户改完大纲再恢复执行。
- 执行轨迹可审计：步骤状态、耗时、证据编号、Reviewer 问题清单全部持久化。

与 `data-agent`（单 ReAct 循环）、`local-pdf-rag`（单轮 RAG）形成对照：前者是「一个 Agent 反复调工具」，本项目是「多个角色按状态机协作」。

## 2. 范围边界

### 首期做

- 资料库：上传 PDF / TXT / MD，解析切分入库，删除文档时级联删除片段；历史运行的证据保留文件名与摘要快照。
- 调研运行：创建、阶段执行、大纲暂停、恢复、取消、失败记录、报告下载。
- 五个固定角色：Planner、Researcher、Analyst、Writer、Reviewer。
- BM25 关键词检索（中文 2-gram）。
- 单页三列工作台，SSE 实时刷新阶段时间线。

### 首期不做

- 用户认证与多租户（本地单用户）。
- 联网搜索（资料只来自本地资料库）。
- 向量检索（保留 `Retriever` 协议，BM25 为首个实现）。
- 报告模板与样式自定义。
- 执行中途崩溃的精确恢复（只有 `awaiting_outline` 跨进程可恢复）。
- 按 Reviewer 建议自动重写（只展示问题清单，由人决定）。
- 多 run 并发执行（全局同时只允许 1 个执行态 run）。
- 前端自动化 E2E（仅一次手动冒烟）。

## 3. 角色设计

| 角色 | 输入 | 输出 | 调 LLM | 落库 |
| --- | --- | --- | --- | --- |
| Planner | 主题 + 资料库概览（文件名/片段数） | 3–6 个子问题 + 拆解理由 | 是 | `sub_questions` |
| Researcher | 单个子问题 | Top-5 片段（文档、页码、分数） | 否 | `evidence` |
| Analyst | 子问题 + 该子问题的证据 | 要点列表，每条带证据编号 | 是 | step 输出摘要 |
| Writer | 全部要点 + 证据表 | Markdown 报告 | 是 | `runs.report_markdown` |
| Reviewer | 报告 + 证据表 | 问题清单 + 总体结论 | 是 | `runs.review_issues` |

关键约束：

- **Researcher 不调 LLM**，是纯检索工具，保证引用可复现、可单测。
- Planner 提示词要求 3–6 条，用户在大纲暂停点可改为 **1–8 条**（守卫上限），两者不冲突：3–6 是生成建议，1–8 是系统约束。
- Analyst 与 Writer 的编号口径见第 7 节；Researcher 检索到的每条证据在 run 内获得全局连续编号，Writer 引用越界编号属于缺陷，由 Reviewer 检出。

## 4. 架构与目录

```
multi-agent-research/
├── backend/
│   ├── app/
│   │   ├── config.py              # pydantic-settings，显式 env_file
│   │   ├── db.py                  # SQLAlchemy 2.0 async engine/session
│   │   ├── models.py              # 6 张表
│   │   ├── schemas.py             # 请求/响应模型
│   │   ├── retrieval/
│   │   │   ├── chunker.py         # 800/100 滑窗切分
│   │   │   ├── tokenizer.py       # 中文 2-gram 分词
│   │   │   ├── bm25.py            # BM25 打分与排序
│   │   │   ├── base.py            # Retriever 协议
│   │   │   └── ingest.py          # PDF/TXT/MD 解析入库
│   │   ├── agents/
│   │   │   ├── base.py            # Agent 协议与 JSON 解析重试
│   │   │   ├── prompts.py         # 五个角色的 prompt 模板
│   │   │   ├── planner.py
│   │   │   ├── researcher.py
│   │   │   ├── analyst.py
│   │   │   ├── writer.py
│   │   │   └── reviewer.py
│   │   ├── orchestrator/
│   │   │   ├── state.py           # 状态枚举、转移表、守卫
│   │   │   ├── runner.py          # 阶段执行器与后台任务注册表
│   │   │   └── events.py          # 进程内事件总线（SSE 广播）
│   │   ├── services/llm.py        # DeepSeek 客户端（可注入假实现）
│   │   └── api/
│   │       ├── documents.py
│   │       └── runs.py
│   ├── tests/
│   ├── data/                      # 运行期生成：app.db
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── api/                   # documents.ts / runs.ts / http.ts
    │   ├── stores/                # documents / runs / activeRun
    │   ├── components/            # DocumentPanel / RunListPanel / RunDetailPanel
    │   ├── views/WorkbenchView.vue
    │   └── main.ts
    ├── package.json
    └── vite.config.ts             # 代理 /api → 127.0.0.1:8000
```

分层原则：

- `retrieval` 不知道 Agent 与 HTTP；`agents` 不知道数据库与 HTTP，只接收数据、返回结构体；`orchestrator` 知道数据库和 Agent，不知道 HTTP；`api` 只做参数校验与序列化。
- 每个角色一个文件、一个 prompt、一个输出 schema，可单独测试。

### 关键配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 空 | 必填；缺失时创建 run 返回 `500 llm_not_configured` |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容接口地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 生成模型 |
| `CHUNK_SIZE` | `800` | 片段字符数 |
| `CHUNK_OVERLAP` | `100` | 相邻片段重叠字符数 |
| `RESEARCH_TOP_K` | `5` | 每个子问题检索片段数 |
| `MAX_UPLOAD_MB` | `20` | 上传大小上限 |
| `LLM_TIMEOUT` | `120` | LLM 请求超时（秒） |
| `DB_PATH` | `./data/app.db` | SQLite 路径 |

配置类必须显式声明 `model_config = SettingsConfigDict(env_file=..., env_file_encoding="utf-8")`，否则 `.env` 不会加载。

## 5. 数据模型

SQLite（WAL 模式），库文件 `backend/data/app.db`；连接需开启 `PRAGMA foreign_keys=ON`，级联删除才会生效。

### documents

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PK | uuid4 hex |
| filename | TEXT | 原始文件名 |
| ext | TEXT | pdf / txt / md |
| size_bytes | INTEGER | 上传字节数 |
| char_count | INTEGER | 提取文本总字符数 |
| chunk_count | INTEGER | 片段数 |
| created_at | TEXT | UTC ISO 8601 |

### chunks

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PK | uuid4 hex |
| document_id | TEXT FK | 级联删除 |
| position | INTEGER | 文档内片段序号，从 0 开始 |
| page | INTEGER NULL | PDF 页码从 1 开始；TXT/MD 为 NULL |
| start | INTEGER | 在该页/该文件文本中的起始偏移 |
| end | INTEGER | 结束偏移（不含） |
| text | TEXT | 片段正文 |

唯一约束：`(document_id, position)`。

### runs

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PK | uuid4 hex |
| topic | TEXT | 调研主题 |
| status | TEXT | 见第 6 节状态枚举 |
| error_code | TEXT NULL | 失败错误码 |
| error_message | TEXT NULL | 失败详情 |
| report_markdown | TEXT NULL | 最终报告 |
| review_issues | TEXT NULL | Reviewer 问题清单 JSON 数组，未到核查阶段为 NULL |
| created_at / updated_at / finished_at | TEXT | UTC ISO 8601，finished_at 可空 |

### sub_questions

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PK | uuid4 hex |
| run_id | TEXT FK | 级联删除 |
| position | INTEGER | 从 0 开始，决定执行顺序 |
| text | TEXT | 子问题正文 |
| origin | TEXT | `auto`（Planner 生成）/ `user`（用户新增或编辑） |

唯一约束：`(run_id, position)`。

### steps

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PK | uuid4 hex |
| run_id | TEXT FK | 级联删除 |
| agent | TEXT | planner / researcher / analyst / writer / reviewer |
| position | INTEGER | run 内步骤序号，从 0 开始 |
| status | TEXT | running / succeeded / failed / skipped |
| detail | TEXT NULL | 输出摘要（如「生成 4 个子问题」） |
| error | TEXT NULL | 失败原因 |
| started_at / finished_at | TEXT | UTC ISO 8601，finished_at 可空 |

### evidence

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | TEXT PK | uuid4 hex |
| run_id | TEXT FK | 级联删除 |
| sub_question_id | TEXT FK | 所属子问题 |
| chunk_id | TEXT NULL | 命中的片段；文档删除后置 NULL（`ON DELETE SET NULL`） |
| filename | TEXT | 命中文档名快照，文档删除后仍可展示 |
| page | INTEGER NULL | 命中页码快照，TXT/MD 为 NULL |
| rank | INTEGER | run 内全局引用编号，从 1 开始 |
| score | REAL | BM25 分数，保留 4 位小数 |
| snippet | TEXT | 片段前 120 字符 |

唯一约束：`(run_id, rank)`。

设计意图：`steps` 是执行轨迹，`evidence` 是可审计引用；前端时间线与报告引用分别只读这两张表，不依赖进程内存。`evidence` 冗余 `filename` 与 `page` 快照，因此删除文档不会破坏历史运行的引用展示。

## 6. 状态机与执行流程

### 状态枚举

```
pending
planning
awaiting_outline     ← 唯一持久暂停点
researching
analyzing
writing
reviewing
done
failed
cancelled
```

### 转移表

| 从 | 事件 | 到 |
| --- | --- | --- |
| pending | 创建后立即启动 | planning |
| planning | Planner 成功 | awaiting_outline |
| planning | Planner 失败 | failed |
| awaiting_outline | PUT outline | awaiting_outline |
| awaiting_outline | POST resume | researching |
| awaiting_outline | POST cancel | cancelled |
| researching | 检索完成 | analyzing |
| analyzing | 要点完成 | writing |
| writing | 报告完成 | reviewing |
| reviewing | 核查完成 | done |
| 任意执行态 | 角色失败（JSON 重试后仍失败 / LLM 错误） | failed |
| 任意执行态 | POST cancel | cancelled |

守卫：

- 仅 `awaiting_outline` 允许改大纲与恢复；其他状态返回 `409 invalid_state`。
- 大纲条数 1–8，去除空白与重复项；不满足返回 `400 invalid_outline`。
- 全局同时只允许 1 个 run 处于 `planning / researching / analyzing / writing / reviewing`；创建新 run 时冲突返回 `409 busy`。
- 应用启动时（lifespan）把所有非终态 run 置为 `failed`，`error_code = "interrupted"`。**只有 `awaiting_outline` 跨进程可恢复**：它不占用执行位，重启后仍可改大纲并恢复。

### 阶段执行

1. **planning**：写入 agent=planner 的 step（running）→ 调 LLM → 解析并校验 1–8 条子问题（提示词建议 3–6 条）→ 写 `sub_questions` → step 置 succeeded → run 置 `awaiting_outline` → 后台任务结束。
2. **researching**：按 `position` 顺序逐个子问题检索，每个子问题一条 researcher step；证据按「子问题顺序 + 分数降序」统一编号 1..M 写入 `evidence`。首期**顺序执行**，理由：SQLite 单写者、编号确定、失败定位简单；`Retriever` 无状态，后续可安全改为并发。
3. **analyzing**：按顺序对每个子问题调 LLM，输出要点 JSON（每条带证据编号）；step detail 记录要点条数。
4. **writing**：把所有要点与证据表交给 Writer，输出 Markdown，写入 `runs.report_markdown`。
5. **reviewing**：Reviewer 输出问题清单 JSON，写入 `runs.review_issues`，step detail 记录问题条数；完成后 run 置 `done`。
6. 每一步开始/结束都更新 `steps` 并通过事件总线广播。

### 取消与失败

- `cancel` 调用后台任务 `cancel()`；捕获 `CancelledError` 后将当前 running step 置 `skipped`，run 置 `cancelled`。
- 角色异常统一包装为 `StepFailed`，写入 error_code / error_message，run 置 `failed`，已完成步骤保留。
- `failed` / `cancelled` 为终态，不提供原地重试；用户只能以同主题新建 run。

## 7. 检索与切分口径

### 切分

- 默认 800 字符、重叠 100 字符，步长 700；`overlap >= size`、`size <= 0`、`overlap < 0` 抛 `ValueError`。
- PDF 按页切分不跨页；TXT/MD 按全文切分，`page = NULL`。
- 片段 `strip()` 后为空则丢弃。

### 分词（中文 2-gram）

- 输入统一转小写；去除空白与标点，只保留字母、数字与汉字。
- 长度 ≥ 2 的连续串取相邻 2-gram（「多智能体」→ 多智 / 智能 / 能体）；长度为 1 时保留单字。
- 查询与片段使用同一分词函数，保证口径一致。

### BM25

- 参数：`k1 = 1.5`、`b = 0.75`。
- `idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5))`，N 为片段总数。
- 文档长度用 term 总数；空库、空查询、无命中均返回空列表。
- 返回 Top-5（`RESEARCH_TOP_K`），按分数降序；同分按 `chunks.id` 升序保证稳定。

### 证据编号

- run 内全局连续编号，从 1 开始，按「子问题 position 升序 → 分数降序 → chunk id 升序」分配。
- Analyst 的要点只能引用本子问题检索到的编号；Writer 的 `[n]` 必须在 1..M 内。
- Reviewer 负责检出：引用了不存在的编号、断言与证据无关、同一编号对应内容与表述矛盾。

### Retriever 协议

```python
async def search(question: str, top_k: int) -> list[EvidenceHit]
```

`EvidenceHit` 字段：`chunk_id`、`document_id`、`filename`、`page`、`score`、`snippet`。BM25 为首个实现；新增向量或混合实现时保持该签名不变，上层角色与编排器无需改动。

## 8. Prompt 与结构化输出契约

所有结构化输出都用「只返回 JSON，不要 Markdown 代码块」约束；解析时先剥离 ```json 围栏，再 `json.loads`。

| 角色 | 输出 schema |
| --- | --- |
| Planner | `{"sub_questions": ["..."], "rationale": "..."}` |
| Analyst | `{"points": [{"text": "...", "evidence": [1, 3]}]}` |
| Writer | 纯 Markdown 文本（不要求 JSON） |
| Reviewer | `{"issues": [{"severity": "high|medium|low", "claim": "...", "problem": "...", "suggestion": "..."}], "summary": "..."}` |

校验规则：

- Planner：`sub_questions` 为 1–8 个非空字符串，自动去重去空；LLM 输出不合法则重试 1 次，仍失败 → step failed。
- Analyst：`points` 至少 1 条，`evidence` 为整数数组且在本子问题证据编号范围内；越界编号保留但记录到 step detail，交由 Reviewer 检查。
- Writer：输出非空且包含至少一个 `[n]`；否则按失败处理。
- Reviewer：`issues` 可为空数组（表示未发现问题）。

## 9. API 与 SSE 契约

### 资料库

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/documents` | multipart `file`，201 返回文档元数据 |
| GET | `/api/documents` | 列表，创建时间倒序 |
| DELETE | `/api/documents/{id}` | 204，级联删除片段 |

### 运行

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/runs` | `{topic}` → 201；事务内先写 `pending`，置 `planning` 后返回并启动后台 Planner |
| GET | `/api/runs` | 列表，创建时间倒序，含状态与主题 |
| GET | `/api/runs/{id}` | 详情：run（含 `review_issues`）+ sub_questions + steps + evidence |
| PUT | `/api/runs/{id}/outline` | `{sub_questions: string[]}`，仅 `awaiting_outline`，200 返回更新后的子问题 |
| POST | `/api/runs/{id}/resume` | 202，仅 `awaiting_outline` |
| POST | `/api/runs/{id}/cancel` | 202，仅执行态与 `awaiting_outline` |
| DELETE | `/api/runs/{id}` | 204，非执行态可删 |
| GET | `/api/runs/{id}/report.md` | `text/markdown` 下载，仅 `done` |
| GET | `/api/runs/{id}/events` | SSE |

创建 run 前置校验：主题去除空白后非空（否则 `400 empty_topic`）；资料库片段数 > 0（否则 `400 empty_library`）；已配置 `DEEPSEEK_API_KEY`（否则 `500 llm_not_configured`）。

### SSE

- 内容类型 `text/event-stream`，事件名：`snapshot`、`run`、`step`、`error`、`done`。
- 连接建立后先推送一次 `snapshot`（当前 run 状态 + 已有 steps + 子问题 + `review_issues`），再推送增量事件。非执行态连接只收到 `snapshot`，前端拿到快照后主动关闭。
- `step` 事件数据：`{"id","agent","position","status","detail","started_at","finished_at"}`。
- `run` 事件数据：`{"status","error_code"}`。
- 每 15 秒发送注释行 `: ping` 保活。
- 终态（done / failed / cancelled）推送 `done` 后关闭；前端据此停止重连。
- 不做 `Last-Event-ID` 回放；页面刷新重新拉取详情并重连。

## 10. 前端交互

单页三列工作台，Vue 3 + TypeScript + Vite + Element Plus + Pinia。

### 左列：资料库

- 上传区（`el-upload`，接受 `.pdf,.txt,.md`），上传中禁用，成功后刷新列表。
- 列表列：文件名、类型、片段数、创建时间、删除按钮（`el-popconfirm` 二次确认）。

### 中列：任务

- 主题输入 + 「新建调研」按钮；无资料时按钮禁用并提示先上传。
- run 列表：主题、状态徽标（颜色映射：执行中 blue、待确认 warning、完成 success、失败 danger）、创建时间。
- 点击切换右列详情；当前选中的 run 在列表中高亮。

### 右列：详情

- 顶部：主题、状态、错误信息（失败时）。
- 阶段时间线（`el-timeline`）：五个角色 × 状态（等待 / 执行中 / 成功 / 失败 / 跳过）× 耗时。
- `awaiting_outline`：可编辑子问题列表（增删改、上下移），「保存大纲」与「继续执行」两个动作；保存成功后再恢复。
- 执行中：SSE 增量刷新时间线与步骤 detail；「取消」按钮。
- `done`：报告 Markdown 预览（`marked` 解析 + `DOMPurify` 净化）、证据表格（编号 / 文档 / 页码 / 分数 / 摘要）、Reviewer 问题清单（按严重度着色）、「下载 .md」。
- `failed`：错误码与信息，提供「以同主题新建」。

### 状态管理

- `documents` store：列表与 CRUD。
- `runs` store：列表、当前 run 详情、SSE 连接生命周期。
- SSE 在切换到其他 run 或组件卸载时关闭，避免多连接。

### 样式与适配

首期面向桌面端（≥1280px）三列固定布局，不做移动端适配；窄屏出现横向滚动视为已知限制。

## 11. 错误码与守卫

| 场景 | HTTP | code |
| --- | --- | --- |
| 非 PDF/TXT/MD | 400 | `unsupported_file` |
| 超过大小上限 | 400 | `file_too_large` |
| 解析失败 / 加密 PDF | 400 | `parse_failed` |
| 无可提取文本 | 400 | `empty_document` |
| 主题为空 | 400 | `empty_topic` |
| 资料库为空 | 400 | `empty_library` |
| 大纲条数不在 1–8 或全为空 | 400 | `invalid_outline` |
| 状态不允许该操作 | 409 | `invalid_state` |
| 已有执行中的 run | 409 | `busy` |
| 文档不存在 | 404 | `document_not_found` |
| run 不存在 | 404 | `run_not_found` |
| 未配置 API Key | 500 | `llm_not_configured` |
| 上游不可达 / 超时 | 502 | `llm_unreachable` |
| 上游非 200 或结构异常 | 502 | `llm_bad_response` |
| 结构化 JSON 重试后仍不合法 | 502 | `llm_bad_json` |

约定：`detail` 统一为 `{"code": "...", "message": "..."}`，前端按 `code` 做提示，`message` 仅用于展示。

`interrupted` 是应用重启时写入非终态 run 的 `runs.error_code`，不是 HTTP 响应码，不出现在接口返回的 `detail` 中。

## 12. 测试策略

pytest + pytest-asyncio + httpx `ASGITransport`，全部离线；`FakeLLM` 按角色返回固定内容。

| 文件 | 覆盖点 |
| --- | --- |
| `tests/conftest.py` | 临时 DB、临时上传目录、`FakeLLM` autouse 注入、ASGI client |
| `test_chunker.py` | 800/100 重叠、短文本、空白、非法参数 |
| `test_tokenizer.py` | 中文 2-gram、英文数字、标点剔除、单字 |
| `test_bm25.py` | 命中排序、空库、空查询、同分稳定、中文查询 |
| `test_ingest.py` | TXT/MD/PDF 解析、页码、格式校验、大小校验、级联删除 |
| `test_state.py` | 全量合法/非法转移、守卫、启动置 failed |
| `test_agents.py` | 各角色输出解析、JSON 围栏剥离、重试一次、越界编号记录 |
| `test_orchestrator.py` | planning 后停在 awaiting_outline、resume 跑完、cancel、步骤顺序与 evidence 编号确定性 |
| `test_api.py` | 文档 CRUD、run CRUD、outline/resume/cancel、409 与 400 守卫、报告下载 |
| `test_sse.py` | 事件顺序（`snapshot` → run/step → done）、终态关闭 |

规模预期：≥ 35 个用例。前端不做自动化 E2E，交付前做一次手动冒烟：上传 → 新建 → 改大纲 → 继续 → 查看报告与证据 → 下载。

## 13. 关键决策与取舍

| 决策 | 选择 | 理由 | 被否方案 |
| --- | --- | --- | --- |
| 编排实现 | 自研状态机 + DB 持久化 | 依赖少、每个环节可单测、与 ai-chat-lite 后台任务模式一致 | LangGraph（框架抽象重，学习重点偏移）、内存态任务（无法恢复） |
| Agent 组织 | Planner 动态拆解 + 固定角色顺序执行 | 决策点集中在一个可校验的 JSON，执行路径确定 | 完全动态 DAG（图校验与并发调度成本高）、固定线性五步（无决策含量） |
| 检索 | BM25 + 中文 2-gram | 零外部依赖、免分词、可离线测试 | Ollama BGE-M3（本机未安装）、OpenAI Embedding（额外 Key） |
| 人工介入 | 仅大纲一个暂停点 | HITL 语义完整且可测，状态机只多一个状态 | 多节点审批（交互与状态爆炸）、无介入 |
| 并发 | 全局单执行位 | SQLite 单写者、错误定位简单、守卫明确 | 多 run 并发（需队列与限流） |
| 模型接入 | DeepSeek，`LLMClient` 协议 + FakeLLM | 沿用仓库既有 Key 与配置习惯，测试不触网 | 多提供方适配（首期成本翻倍） |
| 轨迹存储 | steps / evidence 落库 | 刷新可恢复、审计可查、前端只读表 | 仅内存事件（刷新即丢） |

## 14. 生产化演进

- **存储**：PostgreSQL 替代 SQLite；`evidence.score` 改 numeric；大数据量下 `chunks` 增加全文索引。
- **任务队列**：单执行位改为 Redis + Celery/RQ 队列，run 状态机不变，执行器改为 worker。
- **检索**：实现 `Retriever` 的向量与混合版本（pgvector），保持 `search(question, top_k)` 接口不变。
- **多实例**：事件总线由进程内队列换成 Redis Pub/Sub，SSE 网关独立部署。
- **报告能力**：模板化、版本对比、Reviewer 建议一键重写（需引入重写循环与上限）。
- **权限**：引入用户与项目隔离，`documents` / `runs` 增加 owner 字段。

## 15. 交付物

- 代码：`multi-agent-research/`（后端 + 前端）
- 文档：本设计说明、实施计划（writing-plans 产出）、实现说明（实现完成后补）
- 索引：`.qoder/docs/README.md` 登记
