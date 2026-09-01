import { ref } from 'vue'
import { queryAgent, type AgentQueryResponse, type AgentStep } from '../api/agent'

export interface ChatMessage {
  role: 'user' | 'agent'
  content: string
  steps?: AgentStep[]
  loading?: boolean
}

export function useAgentChat() {
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)

  async function sendQuestion(question: string) {
    // 添加用户消息
    messages.value.push({ role: 'user', content: question })

    // 添加加载中的 agent 消息
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
      }
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

  return { messages, isLoading, sendQuestion }
}
