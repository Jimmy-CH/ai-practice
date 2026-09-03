<template>
  <div class="chat-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="logo">📚</span>
        <span class="title">知识库</span>
      </div>

      <el-button type="primary" class="new-chat-btn" @click="handleNewChat">
        + 新对话
      </el-button>

      <div class="history-section">
        <div class="section-label">历史对话</div>
        <div class="history-list">
          <div
            v-for="conv in chatStore.conversations"
            :key="conv.id"
            class="history-item"
            :class="{ active: conv.id === chatStore.currentConversationId }"
            @click="chatStore.switchConversation(conv.id)"
          >
            <div class="history-title">{{ conv.title }}</div>
            <div class="history-time">{{ formatTime(conv.createdAt) }}</div>
            <el-icon
              class="delete-btn"
              @click.stop="chatStore.deleteConversation(conv.id)"
            >
              <Delete />
            </el-icon>
          </div>
          <div v-if="chatStore.conversations.length === 0" class="empty-history">
            暂无对话记录
          </div>
        </div>
      </div>

      <div class="sidebar-footer">
        <UploadArea />
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { Delete } from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'
import UploadArea from '@/components/UploadArea.vue'

const chatStore = useChatStore()

function handleNewChat(): void {
  chatStore.createConversation()
}

function formatTime(timestamp: number): string {
  const now = Date.now()
  const diff = now - timestamp
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #f0f0f0;
}

.sidebar-header .logo {
  font-size: 20px;
}

.sidebar-header .title {
  font-size: 16px;
  font-weight: 700;
  color: #333;
}

.new-chat-btn {
  margin: 12px 16px;
  border-radius: 8px;
  background: #4a4ae8;
  border-color: #4a4ae8;
}

.history-section {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0 12px;
}

.section-label {
  font-size: 11px;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 8px 8px 4px;
}

.history-list {
  flex: 1;
  overflow-y: auto;
}

.history-item {
  position: relative;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.history-item:hover {
  background: #f5f5ff;
}

.history-item.active {
  background: #f0f0ff;
  border: 1px solid #d0d0ff;
}

.history-title {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 20px;
}

.history-time {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.delete-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  color: #ccc;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}

.history-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #f56c6c;
}

.empty-history {
  text-align: center;
  color: #ccc;
  font-size: 12px;
  padding: 20px 0;
}

.sidebar-footer {
  border-top: 1px solid #f0f0f0;
  padding: 8px;
}

.main-content {
  flex: 1;
  background: #fafafa;
  overflow: hidden;
}
</style>
