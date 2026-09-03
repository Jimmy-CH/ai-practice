import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatApi } from '@/api/modules'
import type { ChatMessage, Conversation } from '@/types'

const STORAGE_KEY = 'rag-chat-conversations'

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substring(2, 8)
}

function loadFromStorage(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveToStorage(conversations: Conversation[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations))
}

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>(loadFromStorage())
  const currentConversationId = ref<string | null>(
    conversations.value.length > 0 ? conversations.value[0].id : null,
  )

  const currentConversation = computed(() =>
    conversations.value.find((c) => c.id === currentConversationId.value) ?? null,
  )

  const messages = computed(() => currentConversation.value?.messages ?? [])

  function createConversation(): string {
    const conv: Conversation = {
      id: generateId(),
      title: '新对话',
      messages: [],
      createdAt: Date.now(),
    }
    conversations.value.unshift(conv)
    currentConversationId.value = conv.id
    saveToStorage(conversations.value)
    return conv.id
  }

  function switchConversation(id: string): void {
    currentConversationId.value = id
  }

  function deleteConversation(id: string): void {
    conversations.value = conversations.value.filter((c) => c.id !== id)
    saveToStorage(conversations.value)
    if (currentConversationId.value === id) {
      currentConversationId.value =
        conversations.value.length > 0 ? conversations.value[0].id : null
    }
  }

  async function sendMessage(question: string): Promise<void> {
    if (!currentConversationId.value) {
      createConversation()
    }

    const conv = currentConversation.value
    if (!conv) return

    // 设置标题（取第一条消息前 20 字）
    if (conv.messages.length === 0) {
      conv.title = question.length > 20 ? question.substring(0, 20) + '...' : question
    }

    // 添加用户消息
    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: question,
      timestamp: Date.now(),
    }
    conv.messages.push(userMsg)

    // 添加 AI loading 消息
    const aiMsg: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      loading: true,
    }
    conv.messages.push(aiMsg)
    saveToStorage(conversations.value)

    try {
      const response = await chatApi.ask(question)
      aiMsg.content = response.answer
      aiMsg.sources = response.sources
      aiMsg.latencyMs = response.latency_ms
      aiMsg.loading = false
    } catch {
      aiMsg.content = '抱歉，回答生成失败，请重试。'
      aiMsg.loading = false
    }

    saveToStorage(conversations.value)
  }

  return {
    conversations,
    currentConversationId,
    currentConversation,
    messages,
    createConversation,
    switchConversation,
    deleteConversation,
    sendMessage,
  }
})
