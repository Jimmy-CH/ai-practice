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

    messages.value.push({ id: Date.now(), role: 'user', content });
    const aiMessage = { id: Date.now() + 1, role: 'assistant', content: '' };
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
      let pendingContent = ''; // 1. 引入缓冲区，暂存未渲染的内容
      let rafId: number | null = null;

      // 2. 渲染层：使用 requestAnimationFrame 批量更新 DOM，避免卡顿
      const tick = () => {
        if (pendingContent) {
          aiMessage.content += pendingContent;
          pendingContent = '';
          scrollToBottom();
          rafId = requestAnimationFrame(tick);
        } else {
          rafId = null; // 没有待渲染内容时，停止动画帧
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // 保留最后一段可能不完整的行

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonData = JSON.parse(line.substring(6));
              if (jsonData.content) {
                pendingContent += jsonData.content; // 3. 数据进缓冲区，不直接修改响应式变量
                if (rafId === null) rafId = requestAnimationFrame(tick); // 启动渲染帧
              }
              if (jsonData.finished || jsonData.error) {
                if (jsonData.error) pendingContent += `\n[Error: ${jsonData.error}]`;
                // 4. 流结束时，立即 flush 剩余内容
                if (pendingContent) {
                  aiMessage.content += pendingContent;
                  pendingContent = '';
                }
                if (rafId) cancelAnimationFrame(rafId);
                isStreaming.value = false;
                return;
              }
            } catch (e) { /* 忽略解析错误，等待下一个 chunk */ }
          }
        }
      }
      
      // 5. 处理 buffer 中可能残留的尾包数据
      if (buffer.trim() && buffer.startsWith('data: ')) {
         try {
            const jsonData = JSON.parse(buffer.substring(6));
            if (jsonData.content) aiMessage.content += jsonData.content;
         } catch(e) {}
      }

    } catch (err) {
      console.error('Stream fetch failed:', err);
      aiMessage.content = '抱歉，AI 响应出错了，请稍后重试。';
    } finally {
      isStreaming.value = false;
    }
  }

  return { messages, isStreaming, sendMessage };
}
