# AI 运营物料智能生成助手：编辑与审核工作流设计

## 目标

为 `ai-material-generator` 子项目引入**可编辑、可审核**的内容资产管理能力，确保：
- AI 生成的物料可被人工修改润色；
- 修改后的内容必须经过 reviewer 角色审核才能下载/导出；
- 已审核通过的物料再次编辑后自动回落为草稿，重新走审核流程。

## 范围

### 包含
- 后端：SQLite 持久化、用户/资产模型、JWT 认证、资产 CRUD、提交审核、审核动作、状态机。
- 前端：登录页、资产列表页、Markdown 编辑器、审核工作台、角色权限控制。
- 测试：后端单元测试覆盖认证、状态机、权限；前端构建验证。

### 不包含
- 用户注册、密码修改等账号管理功能（仅内置 editor / reviewer 两个测试账号）。
- 版本链、diff 对比、历史回滚（沿用 content-workbench 的覆盖式编辑 + 状态回落方案）。
- 真实发布渠道对接（仍保留生成后下载 Markdown）。

## 现状

当前 `ai-material-generator` 已实现：
- 后端 FastAPI：/api/parse、/api/generate、/api/generate-all。
- 前端单页 Vue3：左侧输入、右侧解析结果与物料生成区。
- 生成结果仅支持复制/下载单页，无法保存、编辑、审核。

## 架构

```
┌─────────────┐      HTTP       ┌─────────────────────────────┐
│   Frontend  │  ────────────▶  │  FastAPI backend            │
│  Vue3+TS    │                 │  - auth (JWT)               │
│  Pinia      │                 │  - materials (assets)       │
│  Router     │                 │  - generator (parse/write)  │
└─────────────┘                 │  - database (SQLite async)  │
                                └─────────────────────────────┘
```

## 数据模型

### User

```python
class User(Base):
    __tablename__ = "users"
    id: int PK
    username: str unique
    password_hash: str
    role: str  # "editor" | "reviewer"
    is_active: bool
```

内置种子账号：
- editor / editor123
- reviewer / reviewer123

### MaterialAsset

```python
class MaterialAsset(Base):
    __tablename__ = "material_assets"
    id: int PK
    owner_id: int FK → users.id
    title: str
    content: str            # Markdown 正文
    material_type: str      # 如 xiaohongshu / wechat / zhihu ...
    audience: str           # 如 internal / user / partner
    status: str             # draft | pending_review | approved | rejected
    source_title: str       # 原始文档标题
    analysis: str           # AI 解析出的四类要点 JSON 文本
    review_comment: str | None
    created_at: datetime
    updated_at: datetime
```

## API 设计

### 认证

- `POST /api/auth/login`
  - Body: `{ "username": "editor", "password": "editor123" }`
  - Response: `{ "access_token": "...", "token_type": "bearer", "role": "editor" }`
- `GET /api/auth/me`
  - Response: `{ "id": 1, "username": "editor", "role": "editor" }`

### 生成（扩展）

- `POST /api/generate` 与 `POST /api/generate-all` 保持不变。
- 新增 `POST /api/materials/from-generation`
  - Body: `{ "title", "content", "material_type", "audience", "source_title", "analysis" }`
  - 将生成结果保存为当前用户的 `draft` 资产并返回资产 ID。

### 资产管理

- `GET /api/materials`
  - editor：仅返回自己创建的资产。
  - reviewer：返回全部资产。
  - 支持 `?status=` 过滤。
- `GET /api/materials/{id}`
  - editor 只能查看自己的资产；reviewer 可查看全部。
- `PUT /api/materials/{id}`
  - 仅 owner（editor）可编辑；仅 `draft` 或 `rejected` 状态可编辑。
  - approved 资产被编辑后，状态强制变为 `draft`。
  - Body: `{ "title", "content", "material_type", "audience" }`
- `DELETE /api/materials/{id}`
  - 仅 owner 可删除；仅 `draft`/`rejected` 可删除。
- `POST /api/materials/{id}/submit`
  - 仅 owner；仅 `draft`/`rejected` → `pending_review`。
- `POST /api/materials/{id}/reviews`
  - 仅 reviewer；Body: `{ "action": "approve" | "reject", "comment": "" }`。
  - `approve`：pending_review → approved。
  - `reject`：pending_review → rejected，记录 review_comment。
- `GET /api/materials/pending`
  - 仅 reviewer；列出所有 `pending_review` 资产。
- `GET /api/materials/approved`
  - 登录用户均可；列出所有 `approved` 资产。

### 下载

- `GET /api/materials/{id}/download`
  - 仅 `approved` 资产可下载。
  - editor 只能下载自己的；reviewer 可下载全部。
  - Response: `text/markdown`。

## 状态机

```
              ┌──────────────┐
              │    draft     │
              └──────┬───────┘
                     │ submit
                     ▼
              ┌──────────────┐
    ┌──────── │ pending_review│
    │ reject  └──────┬───────┘
    │                │ approve
    ▼                ▼
┌───────┐      ┌──────────┐
│rejected│      │ approved │
└───┬───┘      └────┬─────┘
    │               │ edit
    └──────────────▶│draft
```

- 编辑 approved 资产后状态自动回落为 draft。
- pending_review 资产禁止编辑。

## 前端路由与权限

| 路由 | 组件 | 角色 |
|---|---|---|
| `/login` | LoginView | 公开 |
| `/` | GeneratorView | editor |
| `/materials` | MaterialListView | editor（自己）/ reviewer（全部） |
| `/materials/:id/edit` | MaterialEditorView | owner editor |
| `/review` | ReviewView | reviewer |
| `/approved` | ApprovedListView | editor / reviewer |

## 安全

- 密码使用 `passlib[bcrypt]` 存储 hash。
- JWT 使用 `python-jose[cryptography]` 签发，过期时间 24 小时。
- 敏感配置（SECRET_KEY、JWT 算法）通过 `.env` 注入，示例值仅用于开发。
- CORS 保持 `allow_origins=["*"]` 以适配本地开发。

## 测试策略

- 后端：
  - `test_auth.py`：登录成功/失败、JWT 解析、角色校验。
  - `test_materials.py`：CRUD、状态机、权限边界、approved 编辑回落、pending 禁止编辑、reviewer 审核。
  - `test_download.py`：仅 approved 可下载、权限边界。
- 前端：`npm run build` 通过。

## 依赖变更

### 后端新增
- `sqlalchemy[asyncio]==2.0.40`
- `aiosqlite==0.21.0`
- `passlib[bcrypt]==1.7.4`
- `python-jose[cryptography]==3.4.0`
- `python-multipart`（已存在，用于登录表单）

### 前端新增
- `vue-router==4.5.0`
- `pinia==3.0.1`

## 迁移与数据初始化

- 启动时自动创建所有表（`Base.metadata.create_all`）。
- 启动时若 users 表为空，则插入 editor / reviewer 两个内置账号。
- 已存在的 generator API 行为不变。
