# AI 运营物料生成助手：生成物料缓存设计

## 背景

当前 `ai-material-generator` 每次切换物料类型或点击「重新生成」时，都会调用 `/generate` 接口，后者再调用 DeepSeek API 生成物料内容。对于同一组输入（文档标题、受众、物料类型），重复生成既浪费 API token，也导致结果不稳定。

本设计为生成的物料内容引入缓存机制，避免重复调用大模型。

## 目标

1. 将生成的物料内容按 `owner_id + source_title + audience + material_type` 持久化到后端 SQLite。
2. 后续相同组合调用 `/generate` 时直接返回缓存内容，**不再调用大模型**。
3. 覆盖规则：同一组合只保留最新生成结果。
4. 前端切换受众、物料类型或点击「重新生成」时，自动使用缓存结果。

## 非目标

- 不替代 `MaterialAsset` 审核资产表；缓存表仅用于减少重复生成。
- 不引入缓存失效时间（TTL），以覆盖式更新为主。
- 不修改现有编辑/审核工作流。

## 架构

新增独立的 `GeneratedMaterial` 资源，与 `MaterialAsset`、`ParsedAnalysis` 解耦：

- `ParsedAnalysis`：保存「文档 → 四类要点」的映射。
- `GeneratedMaterial`：保存「source_title + audience + material_type → 物料内容」的映射。
- `MaterialAsset`：保存用户主动保存的、需要审核的物料资产。

生成接口保持现有入参和出参签名，仅内部增加缓存读写逻辑。

## 数据模型

### GeneratedMaterial

```python
class GeneratedMaterial(Base):
    __tablename__ = "generated_materials"
    __table_args__ = (
        UniqueConstraint("owner_id", "source_title", "audience", "material_type", name="uix_generated_material"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    audience: Mapped[str] = mapped_column(String(64), nullable=False)
    material_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

唯一约束 `(owner_id, source_title, audience, material_type)` 保证同一用户同一组合只保留最新结果。

## API 设计

### 1. 生成单份物料（变更）

```http
POST /api/generate
Content-Type: application/json
```

请求体与现在一致：

```json
{
  "title": "网点管家 V3.2.0 版本迭代说明",
  "analysis": { "新增功能": [...], ... },
  "audience": "网点管理员",
  "material_type": "version_announcement"
}
```

处理流程：
1. 校验当前用户为 `editor` 角色。
2. 检查 `(owner_id, title, audience, material_type)` 是否已存在 `GeneratedMaterial` 缓存。
3. 若存在，直接返回缓存内容（不调用模型）。
4. 若不存在，调用 `generate_material`，将结果 upsert 到 `GeneratedMaterial`，再返回。

返回示例：

```json
{
  "title": "...",
  "content": "...",
  "audience": "网点管理员",
  "material_type": "version_announcement",
  "meta": { ... }
}
```

> 出参与现在保持一致，前端无需改动接口调用。

### 2. 生成全部物料（变更）

```http
POST /api/generate-all
Content-Type: application/json
```

处理流程：
1. 校验当前用户为 `editor` 角色。
2. 对 6 种物料类型分别查询缓存；命中则直接使用，未命中则调用模型生成并保存。
3. 返回 6 份物料的集合。

返回示例：

```json
{
  "audience": "网点管理员",
  "materials": [ ... ]
}
```

## 服务层设计

新增 `app/services/generated_material_service.py`：

```python
async def get_generated_material(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    audience: str,
    material_type: str,
) -> GeneratedMaterial | None:
    ...

async def upsert_generated_material(
    session: AsyncSession,
    owner_id: int,
    source_title: str,
    audience: str,
    material_type: str,
    content: str,
) -> GeneratedMaterial:
    ...
```

## 前端交互

### GeneratorView

- 切换受众或物料类型时，调用 `/generate`；后端自动返回缓存或新内容。
- 点击「重新生成」时，同样调用 `/generate`；命中缓存则快速返回。
- 前端不增加额外状态，依赖后端缓存。

### 提示信息

当命中缓存时，可在后端响应中增加标记 `cached: true`，前端据此提示「已使用历史生成结果」。为保持接口兼容，该字段可选。

## 权限

- `POST /api/generate` 与 `POST /api/generate-all`：需登录且角色为 `editor`。
- `GeneratedMaterial` 按 `owner_id` 隔离，用户只能读取自己的缓存。

## 测试策略

### 后端

1. 首次生成单份物料时调用模型并保存缓存。
2. 同一组合再次生成时直接返回缓存，不调用模型。
3. 生成全部物料时部分命中、部分未命中的混合场景。
4. 非 editor 角色调用生成接口返回 403。

### 前端

1. `npm run build` 通过。
2. 切换物料类型与重新生成功能正常。

## 兼容性

- 数据库新增 `generated_materials` 表，由 `Base.metadata.create_all` 自动创建。
- `/generate` 与 `/generate-all` 增加认证要求，前端 `client.ts` 拦截器会自动处理 401 跳转。
- 生成接口的入参与出参保持不变，现有前端调用无需修改。
