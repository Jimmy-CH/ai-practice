<template>
  <div class="chat-view">
    <!-- 顶部标题栏 -->
    <header class="chat-header">
      <div class="header-title">RAG 知识库助手</div>
      <div class="header-version">v2.0</div>
    </header>

    <!-- 消息列表 -->
    <div ref="messageListRef" class="message-list" @scroll="handleScroll">
      <!-- 空状态 -->
      <div v-if="chatStore.messages.length === 0" class="empty-state">
        <div class="empty-icon">📚</div>
        <div class="empty-title">RAG 知识库助手</div>
        <div class="empty-desc">基于企业文档的智能问答系统，上传文档后即可开始提问</div>
        <div class="example-questions">
          <div
            v-for="q in exampleQuestions"
            :key="q"
            class="example-item"
            @click="handleExampleClick(q)"
          >
            {{ q }}
          </div>
        </div>
      </div>

      <!-- 消息列表 -->
      <template v-else>
        <ChatMessage
          v-for="msg in chatStore.messages"
          :key="msg.id"
          :message="msg"
        />
      </template>
    </div>

    <!-- 底部输入区 -->
    <footer class="chat-footer">
      <div class="input-wrapper">
        <span class="attach-icon">📎</span>
        <textarea
          ref="inputRef"
          v-model="inputText"
          class="chat-input"
          placeholder="输入你的问题..."
          rows="1"
          :disabled="isSending"
          @keydown="handleKeydown"
          @input="autoResize"
        />
        <button
          class="send-btn"
          :disabled="!inputText.trim() || isSending"
          @click="handleSend"
        >
          ↑
        </button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import ChatMessage from '@/components/ChatMessage.vue'

const chatStore = useChatStore()
const inputText = ref('')
const isSending = ref(false)
const messageListRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const userScrolled = ref(false)

const exampleQuestions = [
  '企业知识库支持哪些文档格式？',
  '如何上传文档到知识库？',
  'RAG 检索是如何工作的？',
]

// 新消息时自动滚动到底部（除非用户手动上滑）
watch(
  () => chatStore.messages.length,
  () => {
    if (!userScrolled.value) {
      nextTick(() => scrollToBottom())
    }
  },
)

// 切换会话时重置滚动状态
watch(
  () => chatStore.currentConversationId,
  () => {
    userScrolled.value = false
    nextTick(() => scrollToBottom())
  },
)

function scrollToBottom(): void {
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

function handleScroll(): void {
  if (!messageListRef.value) return
  const { scrollTop, scrollHeight, clientHeight } = messageListRef.value
  userScrolled.value = scrollHeight - scrollTop - clientHeight > 50
}

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

async function handleSend(): Promise<void> {
  const question = inputText.value.trim()
  if (!question || isSending.value) return

  inputText.value = ''
  resetTextareaHeight()
  isSending.value = true
  userScrolled.value = false

  try {
    await chatStore.sendMessage(question)
  } finally {
    isSending.value = false
    nextTick(() => scrollToBottom())
  }
}

function handleExampleClick(question: string): void {
  inputText.value = question
  handleSend()
}

function autoResize(): void {
  const textarea = inputRef.value
  if (!textarea) return
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px'
}

function resetTextareaHeight(): void {
  if (inputRef.value) {
    inputRef.value.style.height = 'auto'
  }
}
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.header-version {
  font-size: 12px;
  color: #999;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-title {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 14px;
  color: #999;
  margin-bottom: 24px;
}

.example-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 500px;
}

.example-item {
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 20px;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}

.example-item:hover {
  border-color: #4a4ae8;
  color: #4a4ae8;
  background: #f8f8ff;
}

/* 底部输入区 */
.chat-footer {
  padding: 12px 20px;
  background: #fff;
  border-top: 1px solid #eee;
  flex-shrink: 0;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: #f5f5f5;
  border-radius: 12px;
  padding: 10px 14px;
}

.attach-icon {
  font-size: 18px;
  cursor: pointer;
  flex-shrink: 0;
  padding-bottom: 2px;
}

.chat-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  outline: none;
  font-family: inherit;
  min-height: 24px;
  max-height: 120px;
}

.chat-input::placeholder {
  color: #bbb;
}

.chat-input:disabled {
  opacity: 0.6;
}

.send-btn {
  width: 32px;
  height: 32px;
  background: #4a4ae8;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.2s;
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-btn:not(:disabled):hover {
  background: #3636c9;
}
</style>
