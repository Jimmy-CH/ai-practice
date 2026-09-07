import { ref } from 'vue'
import { queryAgent, type AgentQueryResponse, type AgentStep } from '../api/agent'
import { saveMessage } from '../api/conversation'
import {
  getConversations, getMessages, createConversation, deleteConversation,
  type ConversationOut,
} from '../api/conversation'

export interface ChatMessage {
  role: 'user' | 'agent'
  content: string
  steps?: AgentStep[]
  loading?: boolean
  chart_data?: any
}

const conversations = ref<ConversationOut[]>([])
const currentConvId = ref<number | null>(null)
const messages = ref<ChatMessage[]>([])
const isLoading = ref(false)

export function useAgentChat() {
  async function loadConversations() {
    try {
      conversations.value = await getConversations()
    } catch { /* ignore */ }
  }

  async function selectConversation(convId: number) {
    currentConvId.value = convId
    try {
      const msgs = await getMessages(convId)
      messages.value = msgs.map(m => ({
        role: m.role as 'user' | 'agent',
        content: m.content,
        steps: m.steps,
        loading: false,
      }))
    } catch {
      messages.value = []
    }
  }

  async function startNewConversation() {
    const conv = await createConversation()
    conversations.value.unshift(conv)
    currentConvId.value = conv.id
    messages.value = []
  }

  async function removeConversation(convId: number) {
    await deleteConversation(convId)
    conversations.value = conversations.value.filter(c => c.id !== convId)
    if (currentConvId.value === convId) {
      currentConvId.value = null
      messages.value = []
    }
  }

  async function sendQuestion(question: string) {
    // 如果没有当前会话，自动创建
    if (!currentConvId.value) {
      const conv = await createConversation(question.slice(0, 20))
      conversations.value.unshift(conv)
      currentConvId.value = conv.id
    }

    messages.value.push({ role: 'user', content: question })
    const agentMsg: ChatMessage = { role: 'agent', content: '', loading: true }
    messages.value.push(agentMsg)
    isLoading.value = true

    try {
      const result = await queryAgent(question)
      const idx = messages.value.length - 1
      messages.value[idx] = {
        role: 'agent',
        content: result.answer,
        steps: result.steps,
        loading: false,
        chart_data: (result as any).chart_data,
      }

      // 保存消息到后端
      await saveMessage(currentConvId.value, 'user', question)
      await saveMessage(currentConvId.value, 'agent', result.answer, result.steps)
    } catch (error: any) {
      const idx = messages.value.length - 1
      messages.value[idx] = {
        role: 'agent',
        content: `请求失败: ${error.message}`,
        steps: [],
        loading: false,
      }
    } finally {
      isLoading.value = false
    }
  }

  return {
    messages, isLoading, conversations, currentConvId,
    sendQuestion, loadConversations, selectConversation,
    startNewConversation, removeConversation,
  }
}
