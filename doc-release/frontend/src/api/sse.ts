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

  const connect = async (): Promise<void> => {
    try {
      const resp = await fetch(`/api/runs/${runId}/events`, {
        signal: controller.signal,
        headers: { Accept: 'text/event-stream' },
      })
      if (!resp.ok || !resp.body) {
        throw new Error(`SSE 连接失败：HTTP ${resp.status}`)
      }
      retries = 0
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
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
            onEvent(ev)
            if (ev.event === 'done') {
              closed = true
              controller.abort()
              return
            }
          }
          idx = buffer.indexOf('\n\n')
        }
      }
      if (!closed) throw new Error('SSE 连接中断')
    } catch (err) {
      if (closed || controller.signal.aborted) return
      if (retries >= maxRetries) {
        onError?.(err)
        return
      }
      retries += 1
      setTimeout(connect, 1000 * 2 ** (retries - 1))
    }
  }

  void connect()

  return {
    close: () => {
      closed = true
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
