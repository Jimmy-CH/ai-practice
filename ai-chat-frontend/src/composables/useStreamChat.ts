// src/composables/useStreamChat.ts
import { ref, nextTick } from 'vue';
import request from '@/api/request'; // 引入封装好的 Axios

const MAX_RETRIES = 3;
const REQUEST_TIMEOUT = 60000;

export function useStreamChat() {
  const messages = ref<Array<{ id: number; role: 'user' | 'assistant' | 'system'; content: string }>>([]);
  const isStreaming = ref(false);

  const scrollToBottom = () => {
    nextTick(() => {
      const container = document.querySelector('.message-list');
      container?.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    });
  };

  // 截取历史消息（保护 system 提示词）
  const getTrimmedMessages = () => {
    const systemMsgs = messages.value.filter(m => m.role === 'system');
    const nonSystemMsgs = messages.value.filter(m => m.role !== 'system');
    const recentMsgs = nonSystemMsgs.slice(-20); // 保留最近 20 条
    return [...systemMsgs, ...recentMsgs].map(m => ({ role: m.role, content: m.content }));
  };

  async function sendMessage(content: string) {
    if (!content.trim() || isStreaming.value) return;

    messages.value.push({ id: Date.now(), role: 'user' as const, content });
    const aiMsgId = Date.now() + 1;
    messages.value.push({ id: aiMsgId, role: 'assistant' as const, content: '' });
    
    isStreaming.value = true;
    scrollToBottom();

    let lastSeq = -1;
    let attempt = 0;

    while (attempt <= MAX_RETRIES) {
      try {
        // 使用 Axios 发起 POST 请求（自动携带 Token）
        const response = await request.post('/chat/', {
          messages: getTrimmedMessages(),
          stream: true,
          resume_from: lastSeq, // 断线续传：告诉后端从哪里继续
        }, { 
          responseType: 'stream', // 关键：告诉 Axios 返回流数据
          timeout: REQUEST_TIMEOUT 
        });

        const reader = response.data.getReader();
        const decoder = new TextDecoder();
        let buffer = ''; 
        let pendingContent = ''; 
        let rafId: number | null = null;

        const tick = () => {
          if (pendingContent) {
            const targetMsg = messages.value.find(m => m.id === aiMsgId);
            if (targetMsg) targetMsg.content += pendingContent;
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
                lastSeq = jsonData.seq; // 记录最新序号
                if (jsonData.content) {
                  pendingContent += jsonData.content;
                  if (rafId === null) rafId = requestAnimationFrame(tick);
                }
                if (jsonData.finished || jsonData.error) {
                  if (jsonData.error) pendingContent += `\n[Error: ${jsonData.error}]`;
                  if (pendingContent) {
                    const targetMsg = messages.value.find(m => m.id === aiMsgId);
                    if (targetMsg) targetMsg.content += pendingContent;
                  }
                  if (rafId) cancelAnimationFrame(rafId);
                  isStreaming.value = false;
                  return;
                }
              } catch (e) { /* 忽略解析错误 */ }
            }
          }
        }
        break; // 正常结束，跳出重试循环
      } catch (err: any) {
        attempt++;
        if (attempt > MAX_RETRIES) {
          const targetMsg = messages.value.find(m => m.id === aiMsgId);
          if (targetMsg) targetMsg.content = '抱歉，AI 响应出错了，请稍后重试。';
          isStreaming.value = false;
          return;
        }
        // 指数退避等待
        await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, attempt - 1)));
      }
    }
  }

  return { messages, isStreaming, sendMessage };
}
