<!-- src/components/ChatWindow.vue -->
<template>
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
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useStreamChat } from '../composables/useStreamChat';

const { messages, isStreaming, sendMessage } = useStreamChat();
const inputText = ref('');

const handleSend = () => {
  if (inputText.value.trim()) {
    sendMessage(inputText.value.trim());
    inputText.value = ''; 
  }
};
</script>

<style scoped>
.chat-container { display: flex; flex-direction: column; height: 100vh; max-width: 800px; margin: 0 auto; border: 1px solid #eee; }
.message-list { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
.message-item { display: flex; align-items: flex-start; gap: 10px; }
.message-item.user { flex-direction: row-reverse; }
.avatar { font-size: 24px; }
.content { background: #f0f0f0; padding: 10px 15px; border-radius: 12px; max-width: 70%; line-height: 1.5; white-space: pre-wrap; }
.message-item.user .content { background: #007bff; color: white; }
.input-area { display: flex; padding: 15px; border-top: 1px solid #ddd; gap: 10px; }
input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 8px; outline: none; }
button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; }
button:disabled { background: #ccc; cursor: not-allowed; }
.typing-indicator { color: #888; font-size: 14px; padding-left: 40px; }
</style>