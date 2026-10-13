import { ref } from 'vue'
import { queryAgent, type AgentStep, type HistoryMessage } from '../api/agent'
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
  suggestions?: string[]
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
        role: m.role,
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
    if (!currentConvId.value) {
      const conv = await createConversation(question.slice(0, 20))
      conversations.value.unshift(conv)
      currentConvId.value = conv.id
    }

    // 提取最近 5 轮对话历史
    const historyMsgs: HistoryMessage[] = []
    const nonLoadingMsgs = messages.value.filter(m => !m.loading)
    const recentPairs = nonLoadingMsgs.slice(-10)
    for (const m of recentPairs) {
      historyMsgs.push({ role: m.role, content: m.content })
    }

    const conversationId = currentConvId.value
    messages.value.push({ role: 'user', content: question })
    const agentMsg: ChatMessage = { role: 'agent', content: '', loading: true }
    messages.value.push(agentMsg)
    isLoading.value = true

    try {
      const result = await queryAgent(question, historyMsgs)
      const idx = messages.value.indexOf(agentMsg)
      if (idx >= 0) {
        messages.value[idx] = {
          role: 'agent',
          content: result.answer,
          steps: result.steps,
          loading: false,
          chart_data: result.chart_data,
          suggestions: result.suggestions || [],
        }
      }

      try {
        if (conversationId !== null) {
          await saveMessage(conversationId, 'user', question)
          await saveMessage(conversationId, 'agent', result.answer, result.steps)
        }
      } catch {
        // 持久化失败不应覆盖已经成功返回的回答
      }
    } catch (error: any) {
      const idx = messages.value.indexOf(agentMsg)
      if (idx >= 0) {
        messages.value[idx] = {
          role: 'agent',
          content: `请求失败: ${error.message}`,
          steps: [],
          loading: false,
        }
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
