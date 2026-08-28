// src/composables/useStreamChat.ts
import { ref, nextTick } from 'vue';

// 配置项：可根据实际业务调整
const MAX_RETRIES = 3;          // 最大重试次数
const BASE_DELAY = 1000;        // 初始重试延迟（1秒）
const REQUEST_TIMEOUT = 60000;  // 请求超时时间（60秒，大模型生成较慢，需留足时间）
const MAX_HISTORY_ROUNDS = 10;  // 保留的最大对话轮数（一问一答算1轮）

export function useStreamChat() {
  const messages = ref<Array<{ id: number; role: 'user' | 'assistant' | 'system'; content: string }>>([]);
  const isStreaming = ref(false);

  const scrollToBottom = () => {
    nextTick(() => {
      const container = document.querySelector('.message-list');
      container?.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    });
  };

  /**
   * 对话历史管理：截取最近的对话轮次，并保护 System Prompt
   */
  const getTrimmedMessages = () => {
    const systemMsgs = messages.value.filter(m => m.role === 'system');
    const nonSystemMsgs = messages.value.filter(m => m.role !== 'system');
    
    // 只保留最近的 MAX_HISTORY_ROUNDS * 2 条消息（一问一答）
    const recentMsgs = nonSystemMsgs.slice(-MAX_HISTORY_ROUNDS * 2);
    
    return [...systemMsgs, ...recentMsgs].map(m => ({ role: m.role, content: m.content }));
  };

  /**
   * 带超时和重试策略的 Fetch 请求
   */
  const fetchWithRetry = async (url: string, options: RequestInit, retries = MAX_RETRIES): Promise<Response> => {
    let attempt = 0;
    while (attempt <= retries) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

      try {
        const response = await fetch(url, { ...options, signal: controller.signal });
        clearTimeout(timeoutId);

        // 如果是服务端错误 (5xx)，触发重试
        if (response.status >= 500 && attempt < retries) {
          throw new Error(`Server error: ${response.status}`);
        }
        return response;
      } catch (err: any) {
        clearTimeout(timeoutId);
        attempt++;
        
        // 如果是用户主动取消（例如点击停止生成），直接抛出，不重试
        if (err.name === 'AbortError' && attempt > 1) throw err; 

        if (attempt > retries) throw err;

        // 指数退避等待
        const delay = BASE_DELAY * Math.pow(2, attempt - 1);
        console.warn(`请求失败，${delay}ms 后进行第 ${attempt} 次重试...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    throw new Error('Max retries exceeded');
  };

  async function sendMessage(content: string) {
    if (!content.trim() || isStreaming.value) return;

    // 添加用户消息
    const userMessage = { id: Date.now(), role: 'user' as const, content };
    messages.value.push(userMessage);

    // 添加 AI 占位消息
    const aiMsgId = Date.now() + 1;
    const aiMessage = { id: aiMsgId, role: 'assistant' as const, content: '' };
    messages.value.push(aiMessage);
    
    isStreaming.value = true;
    scrollToBottom();

    try {
      // ✅ 使用带重试的 fetch，并传入裁剪后的历史消息
      const response = await fetchWithRetry('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          messages: getTrimmedMessages(), 
          stream: true 
        })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const reader = response.body!.getReader();
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
              if (jsonData.content) {
                pendingContent += jsonData.content;
                if (rafId === null) rafId = requestAnimationFrame(tick);
              }
              if (jsonData.finished || jsonData.error) {
                if (jsonData.error) pendingContent += `\n[Error: ${jsonData.error}]`;
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

    } catch (err: any) {
      console.error('Stream fetch failed:', err);
      const targetMsg = messages.value.find(m => m.id === aiMsgId);
      if (targetMsg) {
        targetMsg.content = err.name === 'AbortError' 
          ? '请求已超时，请重试。' 
          : '抱歉，AI 响应出错了，请稍后重试。';
      }
    } finally {
      isStreaming.value = false;
    }
  }

  return { messages, isStreaming, sendMessage };
}

