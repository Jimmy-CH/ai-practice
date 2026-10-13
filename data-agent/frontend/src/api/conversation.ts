import { api } from './auth'
import type { AgentStep } from './agent'

export interface ConversationOut {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export interface MessageOut {
  id: number
  role: 'user' | 'agent'
  content: string
  steps: AgentStep[]
  created_at: string
}

export async function getConversations(): Promise<ConversationOut[]> {
  const { data } = await api.get<ConversationOut[]>('/conversations/')
  return data
}

export async function createConversation(title?: string): Promise<ConversationOut> {
  const { data } = await api.post<ConversationOut>('/conversations/', { title: title || '新对话' })
  return data
}

export async function getMessages(convId: number): Promise<MessageOut[]> {
  const { data } = await api.get<MessageOut[]>(`/conversations/${convId}`)
  return data
}

export async function deleteConversation(convId: number): Promise<void> {
  await api.delete(`/conversations/${convId}`)
}

export async function saveMessage(
  convId: number, role: string, content: string, steps?: any[]
): Promise<void> {
  await api.post(`/conversations/${convId}/messages`, { role, content, steps })
}
