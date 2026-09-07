<script setup lang="ts">
import { ref, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { useAgentChat } from '../composables/useAgentChat'
import { exportToCSV, parseObservationTable } from '../utils/export'

use([CanvasRenderer, BarChart, LineChart, PieChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const {
  messages, isLoading, conversations, currentConvId,
  sendQuestion, loadConversations, selectConversation,
  startNewConversation, removeConversation,
} = useAgentChat()

const inputText = ref('')

const quickQuestions = [
  '查询上月销量最高的商品',
  '各品类销售额对比',
  '最近30天订单趋势',
  '哪个客户下单最多',
]

onMounted(() => { loadConversations() })

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

function buildEchartsOption(chartData: any) {
  if (chartData.type === 'pie') {
    return {
      title: { text: chartData.title },
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: '60%',
        data: chartData.x_axis.map((label: string, i: number) => ({
          name: label, value: chartData.series[0].data[i],
        })),
      }],
    }
  }
  return {
    title: { text: chartData.title },
    tooltip: {},
    xAxis: { type: 'category', data: chartData.x_axis },
    yAxis: { type: 'value' },
    series: chartData.series.map((s: any) => ({
      name: s.name, type: chartData.type, data: s.data,
    })),
  }
}

function handleExport(msg: any) {
  const tableData = parseObservationTable(msg.steps || [])
  if (tableData) exportToCSV(tableData, 'query_result')
}
</script>

<template>
  <div style="display: flex; height: calc(100vh - 56px);">
    <!-- 会话列表侧栏 -->
    <div class="conv-sidebar">
      <button class="new-conv-btn" @click="startNewConversation">+ 新对话</button>
      <div
        v-for="conv in conversations" :key="conv.id"
        :class="['conv-item', { active: conv.id === currentConvId }]"
        @click="selectConversation(conv.id)"
      >
        <span class="conv-title">{{ conv.title }}</span>
        <button class="conv-delete" @click.stop="removeConversation(conv.id)">×</button>
      </div>
    </div>

    <!-- 主聊天区域 -->
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
                <div v-if="msg.chart_data" style="margin-top: 12px;">
                  <v-chart :option="buildEchartsOption(msg.chart_data)" style="height: 350px;" autoresize />
                </div>
                <div v-if="msg.steps && msg.steps.length && !msg.loading" style="margin-top: 8px;">
                  <button class="export-btn" @click="handleExport(msg)">📥 导出 CSV</button>
                </div>
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
  </div>
</template>

<style scoped>
.conv-sidebar {
  width: 220px;
  border-right: 1px solid #e5e7eb;
  padding: 12px;
  overflow-y: auto;
  background: #fafafa;
}
.new-conv-btn {
  width: 100%;
  padding: 8px;
  margin-bottom: 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 13px;
}
.new-conv-btn:hover { background: #f3f4f6; }
.conv-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
}
.conv-item:hover { background: #e5e7eb; }
.conv-item.active { background: #dbeafe; }
.conv-title { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.conv-delete {
  background: none; border: none; cursor: pointer; color: #9ca3af;
  font-size: 16px; padding: 0 4px;
}
.conv-delete:hover { color: #ef4444; }

.agent-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-width: 900px;
}
.messages { flex: 1; overflow-y: auto; padding: 20px; }
.message { margin-bottom: 16px; }
.message.user .bubble {
  background: #3b82f6; color: white; border-radius: 12px 12px 0 12px;
  padding: 12px 16px; max-width: 70%; margin-left: auto;
}
.message.agent .bubble {
  background: #f3f4f6; border-radius: 12px 12px 12px 0;
  padding: 12px 16px; max-width: 85%;
}
.loading { color: #6b7280; font-style: italic; }
.steps-panel {
  margin-bottom: 12px; border: 1px solid #e5e7eb;
  border-radius: 8px; padding: 8px; background: #fafafa;
}
.steps-panel summary { cursor: pointer; font-weight: 600; color: #374151; margin-bottom: 8px; }
.step { margin-bottom: 8px; }
.step-tag {
  display: inline-block; color: white; font-size: 12px;
  padding: 2px 8px; border-radius: 4px; margin-right: 8px;
}
.step-content {
  margin: 4px 0 0 0; padding: 6px 10px; background: white;
  border-radius: 4px; font-size: 13px; white-space: pre-wrap; word-break: break-all;
}
.answer { font-size: 15px; line-height: 1.6; color: #111827; }
.quick-questions { padding: 8px 20px; display: flex; gap: 8px; flex-wrap: wrap; }
.quick-questions button {
  padding: 6px 12px; border: 1px solid #d1d5db; border-radius: 16px;
  background: white; cursor: pointer; font-size: 13px;
}
.quick-questions button:hover { background: #f3f4f6; }
.input-area { display: flex; gap: 8px; padding: 16px 20px; border-top: 1px solid #e5e7eb; }
.input-area input {
  flex: 1; padding: 10px 14px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px;
}
.input-area button {
  padding: 10px 20px; background: #3b82f6; color: white;
  border: none; border-radius: 8px; cursor: pointer; font-size: 14px;
}
.input-area button:disabled { background: #9ca3af; cursor: not-allowed; }
.export-btn {
  padding: 4px 10px; border: 1px solid #d1d5db; border-radius: 4px;
  background: white; cursor: pointer; font-size: 12px;
}
.export-btn:hover { background: #f3f4f6; }
</style>
