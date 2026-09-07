import { api } from './auth'

export interface AgentStep {
  type: 'thought' | 'action' | 'observation'
  content: string
}

export interface HistoryMessage {
  role: 'user' | 'agent'
  content: string
}

export interface AgentQueryResponse {
  answer: string
  steps: AgentStep[]
  success: boolean
  suggestions?: string[]
}

export async function queryAgent(question: string, history: HistoryMessage[] = []): Promise<AgentQueryResponse> {
  const { data } = await api.post<AgentQueryResponse>('/agent/query', { question, history })
  return data
}

export interface TableSchema {
  table_name: string
  columns: { name: string; type: string; description: string }[]
}

export async function getSchemas(): Promise<TableSchema[]> {
  const { data } = await api.get<{ tables: TableSchema[] }>('/agent/schemas')
  return data.tables
}

export async function* streamQuestion(question: string): AsyncGenerator<{ event: string; data: any }> {
  const token = localStorage.getItem('access_token')
  const response = await fetch('/api/agent/query/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ question }),
  })

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        try {
          yield { event: currentEvent, data: JSON.parse(line.slice(6)) }
        } catch { /* skip malformed */ }
      }
    }
  }
}
