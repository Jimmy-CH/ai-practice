# AI Chat Backend

基于 FastAPI 的 AI 对话后端服务，接入 DeepSeek 大模型，提供 JWT 用户认证与 SSE 流式对话能力，并支持流式输出的断点续传。

## 功能特性

- **用户认证**：注册 / 登录，密码 bcrypt 哈希存储，登录返回 JWT（默认有效期 24 小时）
- **流式对话**：通过 SSE（`text/event-stream`）逐 token 返回模型输出
- **断点续传**：请求携带 `resume_from` 序号，服务端跳过已下发的分片，便于前端断线重连后续接内容
- **全异步架构**：SQLAlchemy 2.0 异步 ORM + `AsyncOpenAI` 客户端
- **自动建表**：应用启动时（lifespan）自动创建数据库表
- **CORS 全开**：便于本地前端联调

## 技术栈

| 类别 | 选型 |
| --- | --- |
| 语言 | Python 3.11 |
| Web 框架 | FastAPI + Uvicorn |
| 数据库 ORM | SQLAlchemy 2.0（异步） |
| 数据库驱动 | aiosqlite（默认）/ aiomysql + PyMySQL |
| 认证 | python-jose（JWT）+ passlib[bcrypt] |
| 模型调用 | openai SDK（指向 DeepSeek 接口） |
| 配置管理 | python-dotenv |

## 目录结构

```
ai-chat-backend/
├── app/
│   ├── api/                 # 路由层
│   │   ├── auth.py          # 注册 / 登录
│   │   ├── chat.py          # 流式对话
│   │   ├── users.py         # 当前用户信息
│   │   └── router.py        # 聚合路由，统一前缀 /api
│   ├── models/
│   │   └── user.py          # User 表模型
│   ├── schemas/             # Pydantic 请求 / 响应模型
│   │   ├── chat.py
│   │   └── user.py
│   ├── services/            # 业务逻辑层
│   │   ├── ai_service.py    # DeepSeek 流式响应生成
│   │   └── user_service.py  # 用户注册 / 登录逻辑
│   ├── auth.py              # 密码哈希、JWT 签发与校验依赖
│   ├── config.py            # 配置项（读取 .env）
│   ├── database.py          # 异步引擎、Session、Base
│   └── main.py              # 应用入口，CORS 与 lifespan
├── requirements.txt
├── .env                     # 环境变量（不应提交到仓库）
└── app.db                   # SQLite 数据库文件（默认配置下生成）
```

## 快速开始

### 1. 准备环境

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env`：

```ini
# DeepSeek API Key，必填
DEEPSEEK_API_KEY=sk-xxxxxxxx

# JWT 签名密钥，生产环境务必替换为随机强密钥
SECRET_KEY=your-super-secret-key-change-in-production

# 数据库连接串，默认使用本地 SQLite
DATABASE_URL=sqlite+aiosqlite:///./app.db
# MySQL 示例：
# DATABASE_URL=mysql+aiomysql://user:password@127.0.0.1:3306/ai_chat
```

其余配置项（模型 Base URL、Token 有效期、签名算法）在 `app/config.py` 中定义。

### 3. 启动服务

```powershell
uvicorn app.main:app --reload
```

启动后访问：

- Swagger 文档：http://127.0.0.1:8000/docs
- ReDoc 文档：http://127.0.0.1:8000/redoc

## API 说明

所有接口统一前缀 `/api`。

### POST `/api/auth/register`

注册用户。

```json
{ "username": "alice", "password": "secret" }
```

成功返回 `{"message": "User registered successfully"}`；用户名已存在返回 400。

### POST `/api/auth/login`

登录并获取 Token。

```json
{ "username": "alice", "password": "secret" }
```

返回：

```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

用户名或密码错误返回 401。

### GET `/api/users/me`

需要请求头 `Authorization: Bearer <token>`，返回当前登录用户：

```json
{ "user_id": 1, "username": "alice" }
```

### POST `/api/chat/`

需要请求头 `Authorization: Bearer <token>`。请求体：

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `messages` | `List[Dict[str, str]]` | 必填 | 对话历史，元素形如 `{"role": "user", "content": "..."}` |
| `model` | `string` | `deepseek-chat` | 模型名称 |
| `stream` | `bool` | `true` | 保留字段，当前接口始终以流式返回 |
| `resume_from` | `int` | `-1` | 续传起点，服务端会跳过 `seq <= resume_from` 的分片 |

响应为 SSE 流，每行格式为 `data: {...}`：

```
data: {"seq": 0, "content": "你", "finished": false}
data: {"seq": 1, "content": "好", "finished": false}
data: {"seq": 2, "finished": true}
```

模型调用异常时返回一条包含 `error` 字段且 `finished` 为 `true` 的分片：

```
data: {"seq": 3, "error": "错误信息", "finished": true}
```

### 调用示例

```bash
# 注册
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret"}'

# 登录取 Token
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret"}'

# 流式对话
curl -N -X POST http://127.0.0.1:8000/api/chat/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"你好"}]}'
```

## 实现要点

- **续传语义**：`seq` 由服务端在本次请求内从 0 递增。续传依赖模型对相同输入产生一致的分片序列，属于轻量级实现，并非严格的一致性保证。
- **密码长度**：bcrypt 限制 72 字节，`get_password_hash` 会先截断超长密码。
- **建表方式**：使用 `Base.metadata.create_all`，仅创建缺失的表，不做迁移。表结构变更需引入 Alembic 或手动处理。

## 生产环境注意事项

- 必须通过环境变量覆盖 `SECRET_KEY`，不要使用代码中的默认值
- `app/main.py` 中的 CORS `allow_origins=["*"]` 应收敛为具体域名
- `app/database.py` 中 `create_async_engine(..., echo=True)` 会打印全部 SQL，建议关闭
- `.env` 与 `app.db` 不应提交到版本库
