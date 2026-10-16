# AI 运营物料生成助手：解析结果持久化与前端编辑设计

## 背景

当前 `ai-material-generator` 每次点击「解析文档」都会调用 DeepSeek API 对原始文档进行解析，产出四类运营要点。该过程存在两个问题：

1. **重复调用模型**：同一文档重复解析时浪费 API token 且结果不稳定。
2. **无法人工干预**：解析出的四类要点若存在偏差，用户无法在前端直接修正，只能修改原始文档重新解析。

本设计引入解析结果持久化机制，并在前端提供条目级编辑能力。

## 目标

1. 解析完成后自动将四类要点存入后端 SQLite，按 `owner_id + source_title` 覆盖。
2. 后续同文档解析直接返回已保存结果，**不再调用模型**。
3. 前端支持对四类要点的每个条目进行增、删、改。
4. 编辑后的解析结果可作为「重新生成」物料的输入。

## 非目标

- 不对原始文档内容做版本管理。
- 不引入复杂的 diff/merge 能力，编辑为覆盖式保存。
- 不修改现有的编辑/审核工作流（已审核资产再次编辑自动回落规则保持不变）。

## 架构

新增独立的 `ParsedAnalysis` 资源，与 `MaterialAsset` 解耦：

- `ParsedAnalysis` 负责保存「文档 → 四类要点」的映射。
- `MaterialAsset` 继续负责保存「生成的单份物料内容及其审核状态」。
- 生成接口保持现有签名，前端可选择使用已编辑的 `analysis` 数据调用生成。

## 数据模型

### ParsedAnalysis

```python
class ParsedAnalysis(Base):
    __tablename__ = "parsed_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)

    # 四类要点以 JSON 数组字符串形式存储
    new_features: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    changes: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    notices: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    risks: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

唯一约束：`(owner_id, source_title)`，保证同一用户同一文档标题只保留最新解析结果。

## API 设计

### 1. 解析文档（变更）

```http
POST /api/parse
Content-Type: multipart/form-data
```

请求参数与现在一致：`title`、`content`、`file`。

处理流程：
1. 检查当前用户是否已存在 `(owner_id, title)` 的 `ParsedAnalysis`。
2. 若存在，直接返回已保存结果（不调用模型）。
3. 若不存在，调用 `analyze_document`，将结果 upsert 到 `ParsedAnalysis`，再返回。

> 注：`/api/parse` 目前为匿名接口。为满足「当前用户」语义，本次改为需要 JWT 认证；未登录时返回 401，引导用户先登录。

返回示例：

```json
{
  "analysis_id": 12,
  "title": "网点管家 V3.2.0 版本迭代说明",
  "新增功能": ["异常件一键上报"],
  "变更与优化": ["导入失败返回具体原因"],
  "注意事项": ["需升级至 V3.2.0"],
  "风险提示": ["派费数据存在 24 小时延迟"]
}
```

### 2. 获取解析结果

```http
GET /api/analyses/{source_title}
```

返回当前登录用户对应该 source_title 的解析结果。不存在时返回 404。

### 3. 更新解析结果

```http
PUT /api/analyses/{analysis_id}
Content-Type: application/json

{
  "new_features": ["异常件一键上报"],
  "changes": ["导入失败返回具体原因"],
  "notices": ["需升级至 V3.2.0"],
  "risks": ["派费数据存在 24 小时延迟"]
}
```

仅允许所有者更新。返回更新后的完整解析结果。

### 4. 生成接口（不变）

```http
POST /api/generate
POST /api/generate-all
```

前端在调用生成时，使用当前编辑后的 `analysis` 对象作为入参，与现有接口兼容。

## 前端交互

### GeneratorView 调整

1. **解析区域**：
   - 保留现有「重新解析文档」按钮。
   - 解析成功后，自动保存并展示 `analysis_id`。
   - 若同 title 已有保存结果，提示「已使用历史解析结果，未调用模型」。

2. **AI 解析结果卡片**：
   - 每个要点条目右侧显示「编辑」和「删除」图标。
   - 点击「编辑」后该行变为输入框，支持确认/取消。
   - 每类卡片底部显示「添加条目」按钮。
   - 整体区域增加「保存解析结果」主按钮，显式触发 PUT 保存。

3. **物料生成区域**：
   - 在现有「复制/下载/保存为草稿/导出全部」按钮旁增加「重新生成」按钮。
   - 「重新生成」使用当前前端 `analysis` 状态调用 `generateMaterial`，覆盖 `currentMaterial`。

### 类型更新

`AnalysisResult` 接口增加 `analysis_id?: number` 字段。

## 状态机

`ParsedAnalysis` 无复杂状态，仅保存最新快照。覆盖规则由数据库唯一约束 + upsert 实现。

## 权限

- `POST /api/parse`：需登录（JWT）。
- `GET /api/analyses/{source_title}`：仅返回当前用户数据。
- `PUT /api/analyses/{analysis_id}`：仅所有者可更新，否则 403。

## 测试策略

### 后端

1. 首次解析时调用模型并保存结果。
2. 同一 title 再次解析时直接返回数据库结果，不调用模型。
3. 所有者能更新解析结果。
4. 非所有者无法更新他人解析结果。
5. 生成接口使用编辑后的 analysis 能产出对应物料。

### 前端

1. `npm run build` 通过。
2. 解析后编辑条目、保存、重新生成流程可端到端运行。

## 兼容性

- 数据库新增 `parsed_analyses` 表，由 `Base.metadata.create_all` 自动创建。
- `/api/parse` 增加认证，前端需在解析前确保用户已登录；`client.ts` 已存在 401 跳转拦截器。
- 生成接口入参不变，现有物料生成逻辑不受影响。
