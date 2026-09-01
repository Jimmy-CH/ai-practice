import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface AgentStep {
  type: 'thought' | 'action' | 'observation'
  content: string
}

export interface AgentQueryResponse {
  answer: string
  steps: AgentStep[]
  success: boolean
}

export async function queryAgent(question: string): Promise<AgentQueryResponse> {
  const { data } = await api.post<AgentQueryResponse>('/agent/query', { question })
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
