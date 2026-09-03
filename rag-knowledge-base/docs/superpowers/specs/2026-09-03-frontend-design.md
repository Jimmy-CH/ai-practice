# RAG 知识库前端设计方案

## 概述

为现有 RAG 知识库后端（FastAPI）构建 Vue 3 + TypeScript 前端应用。采用对话式聊天界面（现代卡片风格），支持知识库问答、文档上传和聊天历史管理。

## 技术选型

| 类别 | 选择 |
|------|------|
| 框架 | Vue 3 (Composition API) + TypeScript |
| 构建工具 | Vite |
| 组件库 | Element Plus |
| 状态管理 | Pinia |
| HTTP 客户端 | Axios |
| Markdown 渲染 | markdown-it |
| 项目位置 | `frontend/`（与 `backend/` 同级） |

## 项目结构

```
frontend/
├── src/
│   ├── api/
│   │   ├── index.ts            # Axios 实例 & 拦截器
│   │   └── modules.ts          # 按业务模块组织的 API 函数
│   ├── assets/                 # 静态资源（全局样式、图标）
│   ├── components/
│   │   ├── ChatMessage.vue     # 单条消息（支持 Markdown 渲染）
│   │   ├── SourceCard.vue      # 引用来源卡片
│   │   └── UploadArea.vue      # 文档上传拖拽区
│   ├── composables/
│   │   └── useChat.ts          # 聊天逻辑封装
│   ├── layouts/
│   │   └── ChatLayout.vue      # 主布局（侧边栏 + 聊天区）
│   ├── router/
│   │   └── index.ts            # 路由配置
│   ├── stores/
│   │   ├── chat.ts             # 聊天会话 & 消息历史
│   │   └── document.ts         # 文档上传状态
│   ├── types/
│   │   └── index.ts            # TypeScript 类型定义
│   ├── views/
│   │   └── ChatView.vue        # 主聊天页面
│   ├── App.vue
│   └── main.ts
├── index.html
├── vite.config.ts
├── tsconfig.json
├── .env
└── package.json
```

## 布局设计：现代卡片风格

整体采用左右分栏布局：

- **左侧边栏（白色背景，~240px 宽）**
  - 顶部：项目标题 "📚 知识库"
  - "新对话" 按钮
  - 历史对话列表（卡片式，显示标题和时间戳）
  - 底部：文档管理入口、设置入口

- **右侧聊天区域（浅灰背景 #fafafa）**
  - 顶部标题栏（白色背景，显示助手名称）
  - 中间消息流区域
  - 底部输入区域（圆角输入框 + 发送按钮）

### 消息气泡设计

- **用户消息**：右对齐，蓝色背景 (#4a4ae8)，白色文字，圆角 `12px 12px 2px 12px`
- **AI 消息**：左对齐，白色背景卡片，带 AI 头像图标，圆角 `2px 12px 12px 12px`，带阴影
- AI 回答下方展示引用来源标签和耗时信息

## 组件树

```
App.vue
└── ChatLayout.vue
    ├── SidebarPanel.vue
    │   ├── NewChatButton
    │   ├── ChatHistoryList
    │   └── UploadArea.vue
    └── ChatPanel.vue
        ├── ChatHeader
        ├── MessageList
        │   └── ChatMessage.vue
        │       ├── [用户消息] → 右对齐蓝色气泡
        │       └── [AI 消息] → 左对齐白色卡片 + 头像
        │           ├── MarkdownContent（markdown-it 渲染）
        │           ├── SourceCard.vue（引用来源卡片）
        │           └── LatencyBadge（耗时标签）
        └── ChatInput.vue
```

## 数据流

### 问答流程

```
用户输入 → ChatInput.vue emit('send', question)
  → ChatPanel.vue → chatStore.sendMessage(question)
    → 1. 添加用户消息到 messages[]
    → 2. 调用 POST /v1/ask { question, top_k }
    → 3. 响应 { answer, sources[], latency_ms }
    → 4. 添加 AI 消息到 messages[]
    → 5. 持久化会话到 localStorage
  → 渲染：ChatMessage → MarkdownContent + SourceCard[] + LatencyBadge
```

### 文档上传流程

```
UploadArea.vue → 拖拽/选择文件 → emit('upload', file)
  → documentStore.uploadDocument(file)
    → POST /upload (multipart/form-data)
    → 响应 { status, filename, message }
    → ElMessage 通知结果
```

## API 集成

### Axios 配置

```typescript
const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,  // http://localhost:8000
  timeout: 30000,
})
```

### API 模块

```typescript
// chatApi
ask(question: string, topK?: number): Promise<AskResponse>

// documentApi
upload(file: File): Promise<UploadResponse>

// healthApi
check(): Promise<HealthResponse>
```

### TypeScript 类型（与后端 schemas.py 对应）

```typescript
interface AskRequest { question: string; top_k?: number }
interface SourceItem { index: number; source: string; page: number; snippet: string }
interface AskResponse { answer: string; sources: SourceItem[]; latency_ms?: number }
interface UploadResponse { status: string; filename: string; message: string }
interface HealthResponse { status: string; version: string }
```

## 状态管理（Pinia）

### chatStore

| 状态/方法 | 说明 |
|-----------|------|
| `conversations` | 所有会话列表（id, title, messages, createdAt） |
| `currentConversationId` | 当前活跃会话 ID |
| `messages` (getter) | 当前会话的消息列表 |
| `sendMessage(question)` | 发送问题并获取回答 |
| `createConversation()` | 新建会话 |
| `switchConversation(id)` | 切换会话 |
| `deleteConversation(id)` | 删除会话 |
| 持久化 | localStorage |

### documentStore

| 状态/方法 | 说明 |
|-----------|------|
| `uploadStatus` | 上传状态（idle / uploading / success / error） |
| `uploadDocument(file)` | 上传文档 |
| 持久化 | 无（一次性操作） |

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| 后端不可达 | ElMessage.error "服务暂不可用"，输入框禁用灰显 |
| 上传格式错误 | 前端校验拦截，ElMessage.warning 提示仅支持 PDF/TXT |
| 上传文件过大 | 前端校验拦截，提示 50MB 限制 |
| 问答超时（30s） | ElMessage.error "回答超时"，保留问题可重发 |
| 服务端 500 | ElMessage.error 展示后端 detail 信息 |
| 网络断开 | 监听 navigator.onLine，离线时输入框上方显示提示横幅 |

## 关键交互细节

1. **消息发送**：Enter 发送，Shift+Enter 换行。发送中显示 loading 动画（三个跳动的点），禁用输入框。
2. **自动滚动**：新消息自动滚动到底部；用户手动上滑时不强制滚动。
3. **Markdown 渲染**：markdown-it 渲染 AI 回答。引用标注 `[文件名-p页码]` 通过正则替换为可点击的来源标签。
4. **引用来源**：AI 回答下方可折叠面板展示来源列表（文件名、页码、摘要）。
5. **聊天历史**：左侧边栏展示历史会话，点击切换。标题取首条消息前 20 字。支持删除。localStorage 持久化。
6. **文档上传**：侧边栏底部可折叠上传区，支持拖拽和点击选择，显示进度状态。
7. **空状态**：无消息时中央显示欢迎语和示例问题（可点击直接发送）。

## 环境配置

```env
# frontend/.env
VITE_API_BASE_URL=http://localhost:8000
```

## 后端 API 参考

| 接口 | 方法 | 请求体 | 响应体 |
|------|------|--------|--------|
| `/upload` | POST | multipart/form-data (file) | UploadResponse |
| `/v1/ask` | POST | AskRequest { question, top_k? } | AskResponse { answer, sources, latency_ms } |
| `/health` | GET | - | HealthResponse { status, version } |
