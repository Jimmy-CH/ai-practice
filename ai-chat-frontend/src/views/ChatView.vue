<!-- src/views/ChatView.vue -->
<template>
  <div class="app-container">
    <!-- 顶部导航栏 -->
    <header class="navbar">
      <h1>AI 智能助手</h1>
      <button @click="handleLogout" class="logout-btn">退出登录</button>
    </header>

    <!-- 聊天窗口 -->
    <div class="chat-container">
      <div class="message-list">
        <div v-for="msg in messages" :key="msg.id" class="message-item" :class="msg.role">
          <div class="avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
          <div class="content">{{ msg.content }}</div>
        </div>
        <div v-if="isStreaming" class="typing-indicator">AI 正在思考...</div>
      </div>

      <div class="input-area">
        <input 
          v-model="inputText" 
          @keyup.enter="handleSend" 
          placeholder="输入你的问题..." 
          :disabled="isStreaming"
        />
        <button @click="handleSend" :disabled="isStreaming || !inputText.trim()">
          {{ isStreaming ? '生成中...' : '发送' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import { useStreamChat } from '@/composables/useStreamChat';

const router = useRouter();
const userStore = useUserStore();
const { messages, isStreaming, sendMessage } = useStreamChat();
const inputText = ref('');

const handleSend = () => {
  if (inputText.value.trim()) {
    sendMessage(inputText.value.trim());
    inputText.value = ''; 
  }
};

const handleLogout = () => {
  userStore.logout();
  router.push('/login');
};
</script>

<style scoped>
.app-container { display: flex; flex-direction: column; height: 100vh; }
.navbar { display: flex; justify-content: space-between; align-items: center; padding: 15px 30px; background: #fff; border-bottom: 1px solid #eee; }
.navbar h1 { margin: 0; font-size: 18px; }
.logout-btn { padding: 6px 12px; background: #ff4d4f; color: #fff; border: none; border-radius: 4px; cursor: pointer; }

.chat-container { flex: 1; display: flex; flex-direction: column; max-width: 800px; margin: 0 auto; width: 100%; }
.message-list { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
.message-item { display: flex; align-items: flex-start; gap: 10px; }
.message-item.user { flex-direction: row-reverse; }
.avatar { font-size: 24px; }
.content { background: #f0f0f0; padding: 10px 15px; border-radius: 12px; max-width: 70%; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
.message-item.user .content { background: #007bff; color: white; }
.input-area { display: flex; padding: 15px; border-top: 1px solid #ddd; gap: 10px; background: #fff; }
input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 8px; outline: none; }
button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; }
button:disabled { background: #ccc; cursor: not-allowed; }
.typing-indicator { color: #888; font-size: 14px; padding-left: 40px; }
</style>