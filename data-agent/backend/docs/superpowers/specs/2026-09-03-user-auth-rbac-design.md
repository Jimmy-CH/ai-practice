# 用户管理与 RBAC 权限控制 — 设计文档

## 概述

为 Data Analysis Agent 后端增加用户管理模块，实现基于角色的访问控制（RBAC），支持用户注册、登录（用户名/手机号/第三方 OAuth）。

## 技术选型

| 组件 | 方案 |
|------|------|
| 认证方案 | JWT 双 Token（access_token + refresh_token） |
| OAuth 库 | Authlib（统一处理 GitHub、微信 OAuth 流程） |
| JWT 库 | python-jose |
| 密码哈希 | passlib[bcrypt] |
| HTTP 客户端 | httpx（OAuth 回调） |
| 权限粒度 | 角色级（admin / editor / viewer） |

## 模块结构

```
app/
├── auth/                   # 认证与权限模块
│   ├── __init__.py
│   ├── schemas.py          # Token、登录/注册请求响应模型
│   ├── service.py          # JWT 签发/验证、密码哈希
│   ├── dependencies.py     # get_current_user、require_role 等依赖注入
│   └── oauth.py            # Authlib OAuth 客户端配置（GitHub、微信）
├── users/                  # 用户管理模块
│   ├── __init__.py
│   ├── models.py           # User、Role、OAuthAccount 数据模型
│   ├── schemas.py          # 用户 CRUD 的请求/响应模型
│   ├── service.py          # 用户注册/查询/角色分配业务逻辑
│   └── router.py           # 用户管理 API 路由
├── api/
│   ├── agent.py            # 现有 Agent 接口（加认证依赖）
│   ├── auth.py             # 登录/注册/OAuth 回调路由（新增）
│   └── router.py           # 汇总路由
```

**职责划分**：
- `auth/` — 认证（你是谁）+ 权限校验（你能做什么）
- `users/` — 用户数据增删改查
- `api/auth.py` — 公开接口（登录/注册/OAuth）
- `api/agent.py` — 现有接口，通过 `Depends(require_role(...))` 接入权限控制

## 数据模型

### users 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 用户 ID |
| username | String(50), unique | 用户名 |
| email | String(100), unique, nullable | 邮箱 |
| phone | String(20), unique, nullable | 手机号 |
| hashed_password | String(200), nullable | 密码哈希（OAuth 用户可为空） |
| avatar_url | String(500), nullable | 头像 URL |
| is_active | Boolean, default True | 是否启用 |
| role_id | Integer FK → roles.id | 关联角色 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### roles 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 角色 ID |
| name | String(50), unique | 角色名：admin / editor / viewer |
| description | String(200) | 角色描述 |
| permissions | Text (JSON) | 权限码列表，如 `["agent:query", "agent:schemas"]` |

### oauth_accounts 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 记录 ID |
| user_id | Integer FK → users.id | 关联用户 |
| provider | String(20) | 平台标识：github / wechat |
| provider_user_id | String(100) | 第三方平台用户 ID |
| provider_login | String(100), nullable | 第三方平台登录名 |
| access_token | Text | OAuth access_token |
| created_at | DateTime | 绑定时间 |

### 预置角色

| 角色 | 权限 | 说明 |
|------|------|------|
| admin | `["*"]` | 超级管理员，拥有所有权限 |
| editor | `["agent:query", "agent:schemas"]` | 可使用 Agent 查询 |
| viewer | `["agent:schemas"]` | 只读，仅查看表结构 |

## 认证流程

### JWT 双 Token 机制

- **access_token**：15 分钟有效，每次请求携带
- **refresh_token**：7 天有效，用于刷新 access_token
- 前端请求头：`Authorization: Bearer <access_token>`

### 注册流程

```
POST /api/auth/register
    { username, password, email?, phone? }
    ↓
校验用户名/手机号唯一性
    ↓
bcrypt 哈希密码
    ↓
创建用户（默认 viewer 角色）
    ↓
返回用户信息
```

### 登录流程

**方式一：用户名/手机号 + 密码**

```
POST /api/auth/login  { username_or_phone, password }
    ↓
查找用户 → 验证密码 → 签发双 Token
```

**方式二：手机号 + 验证码**

```
POST /api/auth/sms/send  { phone }
    ↓
生成 6 位验证码 → 存入 Redis/内存缓存（5 分钟有效）→ 日志打印验证码（模拟发送）

POST /api/auth/login/sms  { phone, code }
    ↓
校验验证码 → 签发双 Token
```

**方式三：第三方 OAuth**

```
GET /api/auth/oauth/{provider}/authorize
    ↓
重定向到 GitHub/微信授权页

GET /api/auth/oauth/{provider}/callback
    ↓
Authlib 换取 access_token → 获取第三方用户信息
    ↓
查找 oauth_accounts 表：
  - 已绑定 → 直接登录
  - 未绑定 → 自动注册新用户（随机用户名）→ 绑定
    ↓
签发双 Token
```

### 密码安全

- passlib[bcrypt] 哈希，不存储明文
- 密码最少 6 位

## RBAC 权限控制

### 校验流程

```
请求进入 → get_current_user 依赖
    ↓
从 Header 提取 Authorization: Bearer <token>
    ↓
python-jose 解码 JWT → 获取 user_id
    ↓
查数据库获取 User 对象（含 role）
    ↓
校验 is_active=True
    ↓
require_role("admin", "editor") 依赖
    ↓
检查 user.role.name 是否在允许列表中
    ↓
不在 → 403 Forbidden
在 → 放行
```

### 接口权限分配

| 接口 | 方法 | 允许角色 |
|------|------|----------|
| `/api/auth/register` | POST | 公开 |
| `/api/auth/login` | POST | 公开 |
| `/api/auth/login/sms` | POST | 公开 |
| `/api/auth/sms/send` | POST | 公开 |
| `/api/auth/refresh` | POST | 公开（需有效 refresh_token） |
| `/api/auth/oauth/{provider}/authorize` | GET | 公开 |
| `/api/auth/oauth/{provider}/callback` | GET | 公开 |
| `/api/agent/query` | POST | admin, editor |
| `/api/agent/schemas` | GET | admin, editor, viewer |
| `/api/users/me` | GET | 所有登录用户 |
| `/api/users` | GET | admin |
| `/api/users/{id}/role` | PUT | admin |

## 新增配置项

```env
# .env 新增
SECRET_KEY=your_jwt_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
WECHAT_APP_ID=xxx
WECHAT_APP_SECRET=xxx
```

## 新增依赖

```
python-jose[cryptography]
passlib[bcrypt]
authlib
httpx
```

## 错误码定义

| HTTP 状态码 | 场景 |
|-------------|------|
| 400 | 参数校验失败（用户名已存在、密码太短等） |
| 401 | 未登录、token 过期、token 无效 |
| 403 | 已登录但权限不足 |
| 404 | 用户不存在 |
