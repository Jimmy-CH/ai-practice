<template>
  <!-- 用户消息：右对齐蓝色气泡 -->
  <div v-if="message.role === 'user'" class="message-row user-row">
    <div class="bubble user-bubble">{{ message.content }}</div>
  </div>

  <!-- AI 消息：左对齐白色卡片 + 头像 -->
  <div v-else class="message-row assistant-row">
    <div class="avatar">🤖</div>
    <div class="assistant-content">
      <div class="bubble assistant-bubble">
        <!-- Loading 状态 -->
        <div v-if="message.loading" class="loading-dots">
          <span></span><span></span><span></span>
        </div>
        <!-- Markdown 渲染的回答 -->
        <div v-else class="markdown-body" v-html="renderedContent"></div>
      </div>

      <!-- 引用来源 -->
      <div v-if="message.sources && message.sources.length > 0" class="sources-section">
        <div class="sources-toggle" @click="sourcesExpanded = !sourcesExpanded">
          {{ sourcesExpanded ? '收起' : '展开' }}引用来源 ({{ message.sources.length }})
          <el-icon><ArrowDown v-if="!sourcesExpanded" /><ArrowUp v-else /></el-icon>
        </div>
        <div v-show="sourcesExpanded" class="sources-list">
          <SourceCard
            v-for="src in message.sources"
            :key="src.index"
            :source="src"
          />
        </div>
      </div>

      <!-- 耗时 -->
      <div v-if="message.latencyMs != null" class="latency-badge">
        耗时 {{ message.latencyMs }}ms
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import MarkdownIt from 'markdown-it'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import type { ChatMessage as ChatMessageType } from '@/types'
import SourceCard from './SourceCard.vue'

const props = defineProps<{
  message: ChatMessageType
}>()

const sourcesExpanded = ref(false)
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const renderedContent = computed(() => {
  let content = props.message.content
  // 将 [文件名-p页码] 格式的引用替换为高亮标签
  content = content.replace(
    /\[([^\]]+)-p(\d+)\]/g,
    '<span class="cite-tag">[$1-p$2]</span>',
  )
  return md.render(content)
})
</script>

<style scoped>
.message-row {
  display: flex;
  margin-bottom: 16px;
  align-items: flex-start;
}

.user-row {
  justify-content: flex-end;
}

.assistant-row {
  justify-content: flex-start;
  gap: 10px;
}

.avatar {
  width: 32px;
  height: 32px;
  background: #4a4ae8;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.bubble {
  max-width: 70%;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.user-bubble {
  background: #4a4ae8;
  color: #fff;
  border-radius: 14px 14px 2px 14px;
}

.assistant-bubble {
  background: #fff;
  color: #333;
  border-radius: 2px 14px 14px 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.assistant-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 75%;
}

/* Loading 动画 */
.loading-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: #4a4ae8;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 引用来源 */
.sources-section {
  margin-top: 4px;
}

.sources-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #4a4ae8;
  cursor: pointer;
  user-select: none;
}

.sources-toggle:hover {
  color: #3636c9;
}

.sources-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 6px;
}

.latency-badge {
  font-size: 11px;
  color: #bbb;
}

/* Markdown 内引用标签样式 */
:deep(.cite-tag) {
  display: inline-block;
  background: #f0f0ff;
  color: #4a4ae8;
  padding: 0 4px;
  border-radius: 3px;
  font-size: 0.85em;
  cursor: default;
}
</style>
