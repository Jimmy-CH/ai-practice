import type { SseEvent } from '@/types'

export interface SseHandle {
  close: () => void
}

export function subscribeRun(
  runId: string,
  onEvent: (ev: SseEvent) => void,
  onError?: (err: unknown) => void,
  maxRetries = 5,
): SseHandle {
  const controller = new AbortController()
  let closed = false
  let retries = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  // 单个事件块的缓冲上限：对端持续发送不完整数据时不能无限膨胀
  const MAX_BUFFER = 1 << 20

  const connect = async (): Promise<void> => {
    try {
      const resp = await fetch(`/api/runs/${runId}/events`, {
        signal: controller.signal,
        headers: { Accept: 'text/event-stream' },
      })
      if (!resp.ok || !resp.body) {
        throw new Error(`SSE 连接失败：HTTP ${resp.status}`)
      }
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      // 连接建立不代表链路可用：服务端接受后立即断开时必须继续退避，不能把重试次数清零
      let healthy = false
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx = buffer.indexOf('\n\n')
        while (idx !== -1) {
          const block = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          const ev = parseBlock(block)
          if (ev) {
            if (!healthy) {
              healthy = true
              retries = 0
            }
            onEvent(ev)
            if (ev.event === 'done') {
              closed = true
              controller.abort()
              return
            }
          }
          idx = buffer.indexOf('\n\n')
        }
        if (buffer.length > MAX_BUFFER) buffer = ''
      }
      if (!closed) throw new Error('SSE 连接中断')
    } catch (err) {
      if (closed || controller.signal.aborted) return
      if (retries >= maxRetries) {
        onError?.(err)
        return
      }
      retries += 1
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        void connect()
      }, 1000 * 2 ** (retries - 1))
    }
  }

  void connect()

  return {
    close: () => {
      closed = true
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      controller.abort()
    },
  }
}

function parseBlock(raw: string): SseEvent | null {
  if (raw.startsWith(':')) return null   // 心跳
  let event = 'message'
  let data = ''
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  if (!data) return null
  try {
    return { event, data: JSON.parse(data) }
  } catch {
    return null
  }
}
