# AI 运营物料智能生成助手：审核功能核心闭环与审核台账优化设计

## 目标

修复 `ai-material-generator` 审核功能的两个硬伤（审核员看不到内容即可审核、驳回原因编辑者不可见），并补齐审核台账（审核人 / 审核时间 / 审核操作日志），使 生成 → 提交 → 审核 → 反馈 → 修改 → 重提 的闭环真实可用。

## 现状与问题

已实现（勿重复建设）：MaterialAsset 四状态机（draft / pending_review / approved / rejected）、editor/reviewer 角色权限、审核与下载端点、前端五个页面。

| 级别 | 问题 | 位置 |
|------|------|------|
| 🔴 | 审核台表格无内容预览入口，审核员看不到 Markdown 正文 | ReviewView.vue |
| 🔴 | `review_comment` 已落库并随接口返回，但"我的资产"列表不展示，被驳回后不知原因 | MaterialListView.vue |
| 🟠 | 驳回可空原因；通过/驳回共用同一弹窗，语义不分 | ReviewView.vue |
| 🟠 | 无审核台账：未记录审核人与审核时间；无审核操作日志 | material_asset.py / materials.py |
| 🟡 | 提交审核无二次确认；approved 编辑回落 draft 无提示 | MaterialListView.vue |

## 范围

### 包含
- 后端：MaterialAsset 新增 `reviewed_by` / `reviewed_at` 两列；启动时幂等 ALTER 迁移；驳回必填原因校验；审核日志；列表接口返回 `reviewer_username`。
- 前端：审核台内容预览（抽屉 + Markdown）、驳回必填表单、提交时间列；资产列表审核意见展示、提交确认、回落提示；已审核列表审核人/时间列与预览。
- 测试：后端新增审核台账用例；扩展 e2e_smoke.py 真实链路断言。

### 不包含
- 分页 / 搜索 / 批量审核 / 审核历史表（多条记录）/ 数据库迁移工具（alembic）。
- 用户注册、通知系统、版本链。

## 数据模型变更

`MaterialAsset` 新增：

```python
reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

语义：**最近一次审核动作**的审核人与时间。

生命周期：
- 审核通过/驳回时写入；
- 编辑 approved 资产回落 draft 时保留（前端仅在 approved / rejected 状态展示）；
- 重新提交审核（submit）时与 `review_comment` 一并清空，表示进入新审核周期；
- 历史追溯由服务端日志承担（见下）。

### 迁移策略

项目无 alembic，`Base.metadata.create_all` 不会为既有表补列。在 `main.py` lifespan 中增加幂等迁移：`PRAGMA table_info(material_assets)` 检测缺列后 `ALTER TABLE ... ADD COLUMN`。开发库 `materials.db` 数据保留。测试环境每轮 `drop_all/create_all` 不受影响。

## 后端设计

### 服务层（app/services/material_service.py）

- `review_material(session, asset, action, reviewer_id)`：
  - 状态必须为 pending_review；
  - **`action == "reject"` 且 comment 去空白后为空 → 抛 `ValueError("驳回时必须填写驳回原因")`**（API 层转 400）；approve 允许空 comment；
  - 写入 `status` / `review_comment`（strip 后存，空转 None）/ `reviewed_by` / `reviewed_at`。
- `submit_for_review`：除现有 `review_comment = None` 外，一并清空 `reviewed_by` / `reviewed_at`。

### API 层（app/api/materials.py）

- `POST /{id}/reviews` 传入 `user.id`；新增 `logger = logging.getLogger("app.api.materials")`，成功审核后记录：物料 id、action、reviewer id/username、comment。
- 列表端点（`GET /materials`、`GET /pending`、`GET /approved`）：服务层查询改为 `outerjoin(User, User.id == MaterialAsset.reviewed_by)` 返回 `(asset, reviewer_username)` 元组；API 层组装响应。
- 单条端点维持返回 ORM 对象，`reviewer_username` 缺省为 None（前端不用）。

### 响应模型（app/schemas/material.py）

`MaterialOut` 新增：

```python
reviewed_by: int | None = None
reviewed_at: datetime | None = None
reviewer_username: str | None = None
```

## 前端设计

### 公共工具（新增 src/utils/markdown.ts）

- `renderMarkdown(md: string): string`（marked）；`formatTime(value): string`（无时区后缀按 UTC 解析后本地化显示）。
- GeneratorView 改为引用公共函数（删除局部实现）。

### ReviewView（审核工作台）

- 操作列新增"查看"按钮 → `el-drawer`（size 60%）渲染 Markdown 正文，头部显示标题/类型/受众。
- 表格新增"提交时间"列（updated_at）。
- 审核弹窗按 action 区分：
  - 驳回：标题"驳回原因"，textarea 必填（空则 ElMessage 警告且不提交），确认按钮 type=danger "确认驳回"；
  - 通过：标题"审核意见（选填）"，确认按钮 "确认通过"。

### MaterialListView（我的资产）

- 新增"审核意见"列：rejected 展示驳回原因、approved 展示通过备注，`show-overflow-tooltip`；无内容显示 "-"。
- 审核时间并入该列 tooltip（`reviewer_username · reviewed_at`）或紧邻小字展示。
- "提交审核"增加 `ElMessageBox.confirm`（提示提交后不可编辑）。
- approved 资产点击"编辑"时 confirm 提示"保存后将回落为草稿，需重新审核"。

### ApprovedListView（已审核）

- 新增"审核人"（reviewer_username）与"审核时间"列。
- 新增"查看"按钮复用抽屉预览。

## 测试策略

后端（新增至 tests/test_materials.py 或独立文件）：
1. 驳回空 comment → 400 且状态仍为 pending_review；
2. 驳回带 comment → rejected 且 `reviewed_by`/`reviewed_at` 落库、review_comment 保存；
3. 通过后列表接口返回 `reviewer_username == "reviewer"`；
4. rejected 重新提交后 `review_comment`/`reviewed_by`/`reviewed_at` 均清空；
5. 仅空格 comment 驳回 → 400。

前端：`npm run build` 通过。

真实链路：扩展 `e2e_smoke.py` —— 审核通过后断言响应含 `reviewed_by`/`reviewed_at`，`/approved` 列表断言 `reviewer_username == "reviewer"`；补充驳回必填（空原因 400）断言。

## 实施任务分解

1. 后端模型加列 + lifespan 幂等迁移。
2. 服务层：驳回必填校验、台账字段写入、重新提交清空。
3. API 层：列表 outerjoin username、审核日志、响应模型扩展。
4. 后端测试用例 + 全量 pytest。
5. 前端：utils/markdown.ts（并让 GeneratorView 引用）+ ReviewView 改造。
6. 前端：MaterialListView、ApprovedListView 改造 + build。
7. e2e_smoke.py 扩展 + 真实链路验证。
8. 提交 dev 分支。
