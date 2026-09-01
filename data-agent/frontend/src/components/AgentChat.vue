<script setup lang="ts">
import { ref } from 'vue'
import { useAgentChat } from '../composables/useAgentChat'

const { messages, isLoading, sendQuestion } = useAgentChat()
const inputText = ref('')

const quickQuestions = [
  '查询上月销量最高的商品',
  '各品类销售额对比',
  '最近30天订单趋势',
  '哪个客户下单最多',
]

function handleSend() {
  const q = inputText.value.trim()
  if (!q || isLoading.value) return
  inputText.value = ''
  sendQuestion(q)
}

function handleQuick(q: string) {
  if (isLoading.value) return
  sendQuestion(q)
}

function stepColor(type: string): string {
  switch (type) {
    case 'thought': return '#3b82f6'
    case 'action': return '#f59e0b'
    case 'observation': return '#10b981'
    default: return '#6b7280'
  }
}

function stepLabel(type: string): string {
  switch (type) {
    case 'thought': return '💭 Thought'
    case 'action': return '⚡ Action'
    case 'observation': return '👁 Observation'
    default: return type
  }
}
</script>

<template>
  <div class="agent-chat">
    <div class="messages">
      <div v-for="(msg, i) in messages" :key="i" :class="['message', msg.role]">
        <div class="bubble">
          <div v-if="msg.role === 'user'" class="user-text">{{ msg.content }}</div>
          <template v-else>
            <div v-if="msg.loading" class="loading">Agent 正在思考...</div>
            <template v-else>
              <div v-if="msg.steps && msg.steps.length" class="steps-panel">
                <details open>
                  <summary>思考过程 ({{ msg.steps!.length }} 步)</summary>
                  <div v-for="(step, j) in msg.steps" :key="j" class="step">
                    <span class="step-tag" :style="{ background: stepColor(step.type) }">
                      {{ stepLabel(step.type) }}
                    </span>
                    <pre class="step-content">{{ step.content }}</pre>
                  </div>
                </details>
              </div>
              <div class="answer">{{ msg.content }}</div>
            </template>
          </template>
        </div>
      </div>
    </div>

    <div class="quick-questions">
      <button v-for="q in quickQuestions" :key="q" @click="handleQuick(q)" :disabled="isLoading">
        {{ q }}
      </button>
    </div>

    <div class="input-area">
      <input
        v-model="inputText"
        @keyup.enter="handleSend"
        :disabled="isLoading"
        placeholder="输入你的问题..."
      />
      <button @click="handleSend" :disabled="isLoading || !inputText.trim()">发送</button>
    </div>
  </div>
</template>

<style scoped>
.agent-chat {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
  max-width: 900px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message {
  margin-bottom: 16px;
}

.message.user .bubble {
  background: #3b82f6;
  color: white;
  border-radius: 12px 12px 0 12px;
  padding: 12px 16px;
  max-width: 70%;
  margin-left: auto;
}

.message.agent .bubble {
  background: #f3f4f6;
  border-radius: 12px 12px 12px 0;
  padding: 12px 16px;
  max-width: 85%;
}

.loading {
  color: #6b7280;
  font-style: italic;
}

.steps-panel {
  margin-bottom: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  background: #fafafa;
}

.steps-panel summary {
  cursor: pointer;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.step {
  margin-bottom: 8px;
}

.step-tag {
  display: inline-block;
  color: white;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  margin-right: 8px;
}

.step-content {
  margin: 4px 0 0 0;
  padding: 6px 10px;
  background: white;
  border-radius: 4px;
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-all;
}

.answer {
  font-size: 15px;
  line-height: 1.6;
  color: #111827;
}

.quick-questions {
  padding: 8px 20px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.quick-questions button {
  padding: 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 16px;
  background: white;
  cursor: pointer;
  font-size: 13px;
}

.quick-questions button:hover {
  background: #f3f4f6;
}

.input-area {
  display: flex;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid #e5e7eb;
}

.input-area input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
}

.input-area button {
  padding: 10px 20px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}

.input-area button:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}
</style>
