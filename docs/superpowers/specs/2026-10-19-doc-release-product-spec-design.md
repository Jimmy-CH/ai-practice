# doc-release 九节产品说明书生成设计

## 背景与目标

doc-release 现有产物 `product-doc.md` 为八节发布说明（版本概览 / 发布亮点 / 功能清单 / 破坏性变更 / 涉及模块 / 验收清单 / 上线步骤 / 溯源），内容只基于本次变更 diff，无法回答「系统有哪些功能、流程怎么走、领域实体是什么」。

本设计将 `product-doc.md` 调整为九节产品说明书，结构对齐 `doc-release/docs/产品说明.md` 的人工先例：

1. 项目概述
2. 用户角色与使用场景
3. 系统架构与技术栈
4. 功能清单及核心逻辑（`序号 | 功能简介 | 核心逻辑 | 涉及角色 | 优先级`，按模块分组，P0/P1/P2）
5. 核心流程（各模块 mermaid 流程图）
6. 领域实体关系图（mermaid erDiagram）
7. 领域实体清单（分模块字段表 + 枚举字典）
8. 详细规则说明（分模块主题规则 + 错误码矩阵）
9. 非功能性需求（性能/安全/可靠性/部署/可维护/扩展/兼容）

产物类型、文件名（`product-doc.md`）、kind（`document`）均不变；checklist.csv 与 trace.json 保持现有语义。

## 非目标

- 不新增第四类产物，不改 API 路由与 kind 枚举。
- 不做文档在线编辑、不做增量生成（每次运行重新分析目标版本快照）。
- 不改 checklist 的业务口径与 tone 行为。
- 不引入向量检索或代码图谱；上下文通过文件树 + 关键文件内容 + AST 符号提供。

## 总体架构

```
步骤0 resolve → 步骤1 collect → 步骤2 parse
→ 步骤3「LLM 业务化改写与产品说明书生成」
   ├─ rewrite_changes（现有，diff → features）
   └─ generate_product_spec（新增，head_ref 快照 → 结构化 spec）
→ 步骤4 产物生成并归档（render_document 分发九节渲染）
```

- 步骤数保持 5；步骤 3 名称改为「LLM 业务化改写与产品说明书生成」。
- 两个 LLM 任务并发执行：rewrite 沿用 `llm_max_concurrency`（3），spec 使用 `spec_concurrency`（2）。
- 取消沿用协作式标志：spec 在每次 LLM 调用前检查；取消时两个任务都终止。

## 新增/改动模块

| 文件 | 职责 |
|---|---|
| `backend/app/services/spec_service.py` | 快照收集、模块聚类、分模块 LLM 分析、全局概览分析、合并/降级、ER 汇总、指标统计 |
| `backend/app/prompts/spec_v1.py` | `PROMPT_VERSION="spec/v1"`；模块画像与全局概览两套提示词；严格 JSON 契约 |
| `backend/app/services/spec_renderer.py` | 纯函数 `render_product_spec(result, opts)`，确定性输出九节 Markdown |
| `backend/app/services/git_service.py` | 新增 `list_tree(repo_path, ref)`（`git ls-tree -r --name-only`） |
| `backend/app/services/renderers.py` | `render_document` 分发：有 `result["spec"]` 走九节；否则保留旧八节（历史运行兼容） |
| `backend/app/services/pipeline_service.py` | 步骤 3 并发执行 rewrite + spec；日志、结果落库、trace 元数据 |
| `backend/app/services/llm_service.py` | 不新增 provider 逻辑，spec_service 复用 `_chat` / `extract_json` |
| `backend/app/config.py` | `spec_max_modules=12`、`spec_max_files_per_module=12`、`spec_max_file_chars=4000`、`spec_concurrency=2` |

## 快照采集规则

- 文件枚举：`git ls-tree -r --name-only <ref>`，只读，不触碰工作区。
- 跳过目录：`.git`、`node_modules`、`dist`、`build`、`out`、`venv`、`.venv`、`__pycache__`、`.pytest_cache`、`.mypy_cache`、`.idea`、`.vscode`、`archive`、`static`、`coverage`、`.next`、`.nuxt`、`target`、`bin`、`obj`。
- 跳过文件：`.env*`、`*.pem`、`*.key`、`credentials*`、`id_rsa*`、`.npmrc`、`.netrc`、锁文件、压缩包、二进制、minified、>200KB。
- 文本后缀白名单：py/ts/tsx/js/jsx/vue/go/java/kt/rs/cs/rb/php/sql/md/json/yaml/yml/toml/ini/cfg/sh/ps1/gradle/xml/proto。
- 模块键：剥离首个容器目录（backend/frontend/server/client/web/src/app/packages/apps）后取前两级目录；无目录归入「根目录」。
- 模块上限 12：按「含本次变更 > 文件评分 > 文件数」排序；超出模块在第 3 节声明未纳入自动分析。
- 单模块上限 12 个文件、单文件 4000 字符；按路由/控制器/模型/实体/schema/服务/页面/配置优先，测试与示例降权。
- 提示词附带该模块的变更文件与 AST 符号摘要，用于第 4 节标注「本次变更」。

## 数据结构（run.result["spec"]）

```json
{
  "prompt": "spec/v1",
  "snapshot": {"ref": "v1.1.0", "files": 123, "modules": 8, "skipped": 3},
  "overview": {"name": "", "positioning": "", "problems": [], "scope": []},
  "roles": [{"role": "", "scenarios": []}],
  "architecture": {"stack": [{"layer": "", "tech": "", "note": ""}],
                   "modules": [{"name": "", "responsibility": ""}],
                   "diagram": "flowchart TD ..."},
  "modules": [{
    "name": "src/order", "responsibility": "", "changed": true, "degraded": false,
    "functions": [{"name": "", "logic": "", "roles": [], "priority": "P0"}],
    "flows": [{"title": "", "mermaid": "flowchart TD ..."}],
    "entities": [{"name": "", "table": "", "fields": [{"name": "", "type": "", "constraints": "", "note": ""}],
                  "relations": [{"target": "", "label": "", "cardinality": "||--o{"}]}],
    "enums": [{"name": "", "values": []}],
    "rules": [{"topic": "", "points": []}],
    "errorCodes": [{"scene": "", "code": "", "ui": ""}],
    "nfr": {"performance": [], "security": [], "reliability": [], "deployment": [],
            "maintainability": [], "extensibility": [], "compatibility": []}
  }],
  "degradedModules": [], "lowConfidence": [],
  "llm": {"calls": 0, "okCalls": 0, "inputChars": 0, "outputChars": 0}
}
```

结果为结构化数据而非最终 Markdown，保证预览/导出/归档三路同源，且 mask 可在渲染期重算。

## 提示词与校验

- 模块提示词：输入模块名、文件树、关键文件内容、变更文件与符号；输出固定 JSON。硬性要求：只输出 JSON；功能点 1~8 条、优先级 P0/P1/P2；核心逻辑引用真实接口/表/开关；流程图 1~3 张，首行必须是 flowchart/sequenceDiagram/stateDiagram-v2；实体字段来自真实模型/表；规则来自真实校验与状态流转；无证据的数组留空。
- 全局提示词：输入 README 摘要、依赖清单、模块摘要；输出 overview/roles/architecture。
- 校验：复用 `extract_json`；新增字段级校验与默认值（缺失数组补空、优先级非法降为 P1、mermaid 首行白名单、ER 标识符清洗、cardinality 白名单）。
- 重试：单次失败追加「只输出 JSON」重试 1 次；仍失败进入降级。

## 降级策略

- 单模块失败：`degraded=true` + 一条「待人工确认」功能行；记入 `degradedModules` 与 `lowConfidence`；运行终态为 `degraded`。
- 全局概览失败：用 README 首段 + 模块职责 + 清单探测确定性兜底，架构图可缺省。
- 全部模块失败：仍渲染九节骨架并标注待复核，运行不 failed。
- 取消：正常抛 `RunCancelled`，沿用现有取消路径。
- 说明书生成不因任何单点 LLM 失败而中断归档。

## 九节渲染规则

- 标题：`# {repoName} 产品说明书（{version}）`；副标题注明快照 ref、生成时间、生成器、提示词版本、覆盖模块/文件数。
- 第 4 节：按模块分组，序号全局连续；`核心逻辑` 使用技术口径；模块名后标注「本次变更」。
- 第 5 节：每个流程输出 `### 5.x {标题}（{模块}）` + mermaid 代码块；无流程的模块不占小节。
- 第 6 节：合并全部实体（按名称合并字段、关系），输出单张 `erDiagram`；字段类型/名称清洗为合法标识符。
- 第 7 节：分模块字段表（字段/类型/约束默认/说明），末尾「枚举字典」全局表。
- 第 8 节：分模块主题规则（`### 8.x {模块}` + 加粗主题 + 列表），末尾全局错误码矩阵（场景/状态码/前端表现）。
- 第 9 节：固定 7 个主题子节，聚合去重；全空时输出待补充提示。
- 附录：模块 → 关键文件表；结尾输出待复核项。
- mask：模块名与文件路径按现有 `_mask_path` 规则掩码，提交哈希掩码；其余文本不脱敏。
- tone：九节说明书固定技术口径，tone 继续作用于 checklist；文档接口仍接受 tone 参数但不再改变内容。

## 前端 mermaid 渲染

- 新增依赖 `mermaid`（动态 import，独立 chunk）。
- `render/artifacts.ts`：marked 自定义 renderer 把 ```mermaid 代码块输出为 `<div class="mermaid">源码</div>`，经 DOMPurify 净化。
- `OutputPanel.vue`：文档渲染后（`flush: 'post'` + `nextTick`）逐块调用 `mermaid.run`；`securityLevel: 'strict'`；单块失败降级为 `<pre>` + 错误提示，不整页报错；tab/tone/mask 切换后重新渲染。
- CSS：mermaid 容器横向滚动，SVG 自适应宽度。

## 兼容性

- 历史运行无 `result["spec"]`：`render_document` 回退旧八节渲染，详情/导出不报错。
- 产物文件名、kind、下载路由、归档目录、删除保护逻辑不变。
- trace.json 的 `artifacts` 仍为三件；新增 `spec` 元数据（prompt/模块数/降级数/文件数/输入输出字符数），不内嵌全文。
- 步骤数仍为 5，前端步骤名称同步更新。

## 测试计划

- `tests/conftest.py`：`_chat` 打桩按系统提示词标记分流，模块画像与全局概览分别返回合法 JSON。
- `tests/test_spec_service.py`（新）：快照过滤（敏感文件/依赖目录/二进制）、模块聚类与上限、JSON 校验与默认值、单模块降级、概览兜底、ER 汇总、取消传播。
- `tests/test_renderers.py`：九节标题、mermaid 代码块、mask、无 spec 时回退旧八节。
- `tests/test_pipeline.py`：仍 5 步 / 3 产物；`result.spec` 存在；`product-doc.md` 含九节与 mermaid。
- `tests/test_api_runs.py`：document 断言改为九节标题；`_slow_chat` 支持 spec 分流。
- `e2e_smoke.py`：断言九节标题与 mermaid 代码块存在。
- 前端：`npm run build` 通过；手动验证 mermaid 渲染与单图失败降级。

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| 星语长 JSON 不稳定 | 严格 schema + 字段默认值 + 单模块重试 + 降级占位 |
| mermaid 语法非法 | 后端首行白名单校验；前端逐块 try/catch，失败降级代码块 |
| 运行耗时上升 | 模块/文件/字符三重限额；spec 并发独立；SSE 实时日志 |
| 大仓库上下文超限 | 模块上限 12 + 关键文件优先 + 超限声明 |
| 源码泄密 | 敏感文件过滤；mask 仅作用于输出路径 |
