// src/composables/useStreamChat.ts
import { ref, nextTick } from 'vue';

export function useStreamChat() {
  const messages = ref<Array<{ id: number; role: 'user' | 'assistant'; content: string }>>([]);
  const isStreaming = ref(false);

  const scrollToBottom = () => {
    nextTick(() => {
      const container = document.querySelector('.message-list');
      container?.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    });
  };

  async function sendMessage(content: string) {
    if (!content.trim() || isStreaming.value) return;

    // ✅ 修复1：使用 as const 解决 TS 类型报错
    const userMessage = { id: Date.now(), role: 'user' as const, content };
    messages.value.push(userMessage);

    // ✅ 修复2：将 AI 消息也定义为响应式对象，或者通过数组索引修改
    // 这里我们用一个局部变量暂存内容，最后再统一赋值，或者用 ref 包装
    const aiMsgId = Date.now() + 1;
    const aiMessage = { id: aiMsgId, role: 'assistant' as const, content: '' };
    messages.value.push(aiMessage);
    
    isStreaming.value = true;
    scrollToBottom();

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          messages: messages.value.map(m => ({ role: m.role, content: m.content })), 
          stream: true 
        })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = ''; 
      let pendingContent = ''; // ✅ 修复3：引入数据缓冲区
      let rafId: number | null = null;

      // ✅ 修复4：使用 requestAnimationFrame 批量更新 DOM，解决卡顿
      const tick = () => {
        if (pendingContent) {
          // 找到数组中对应的 AI 消息并更新（触发 Vue 响应式）
          const targetMsg = messages.value.find(m => m.id === aiMsgId);
          if (targetMsg) {
            targetMsg.content += pendingContent;
          }
          pendingContent = '';
          scrollToBottom();
          rafId = requestAnimationFrame(tick);
        } else {
          rafId = null;
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; 

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonData = JSON.parse(line.substring(6));
              if (jsonData.content) {
                pendingContent += jsonData.content;
                if (rafId === null) rafId = requestAnimationFrame(tick);
              }
              if (jsonData.finished || jsonData.error) {
                if (jsonData.error) pendingContent += `\n[Error: ${jsonData.error}]`;
                // 流结束时，立即 flush 剩余内容
                if (pendingContent) {
                  const targetMsg = messages.value.find(m => m.id === aiMsgId);
                  if (targetMsg) targetMsg.content += pendingContent;
                  pendingContent = '';
                }
                if (rafId) cancelAnimationFrame(rafId);
                isStreaming.value = false;
                return;
              }
            } catch (e) { /* 忽略解析错误 */ }
          }
        }
      }
      
      // 处理尾包数据
      if (buffer.trim() && buffer.startsWith('data: ')) {
         try {
            const jsonData = JSON.parse(buffer.substring(6));
            if (jsonData.content) {
              const targetMsg = messages.value.find(m => m.id === aiMsgId);
              if (targetMsg) targetMsg.content += jsonData.content;
            }
         } catch(e) {}
      }

    } catch (err) {
      console.error('Stream fetch failed:', err);
      const targetMsg = messages.value.find(m => m.id === aiMsgId);
      if (targetMsg) targetMsg.content = '抱歉，AI 响应出错了，请稍后重试。';
    } finally {
      isStreaming.value = false;
    }
  }

  return { messages, isStreaming, sendMessage };
}
