/** 问答请求体 — 对应后端 AskRequest */
export interface AskRequest {
  question: string
  top_k?: number
}

/** 引用来源条目 — 对应后端 SourceItem */
export interface SourceItem {
  index: number
  source: string
  page: number
  snippet: string
}

/** 问答响应体 — 对应后端 AskResponse */
export interface AskResponse {
  answer: string
  sources: SourceItem[]
  latency_ms?: number
}

/** 文档上传响应体 — 对应后端 UploadResponse */
export interface UploadResponse {
  status: string
  filename: string
  message: string
}

/** 健康检查响应体 — 对应后端 HealthResponse */
export interface HealthResponse {
  status: string
  version: string
}

/** 单条聊天消息 */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceItem[]
  latencyMs?: number
  timestamp: number
  loading?: boolean
}

/** 聊天会话 */
export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
}
