import api from './auth'

export interface AuditLogOut {
  id: number
  user_id: number | null
  username: string
  action: string
  detail: string
  ip_address: string
  created_at: string
}

export interface UsageStats {
  total_queries: number
  today_queries: number
  week_queries: number
  top_users: { username: string; count: number }[]
  top_questions: { question: string; user: string; count: number }[]
  daily_trend: { date: string; count: number }[]
}

export async function getAuditLogs(limit = 100, action?: string): Promise<AuditLogOut[]> {
  const params: any = { limit }
  if (action) params.action = action
  const { data } = await api.get('/audit/logs', { params })
  return data
}

export async function getUsageStats(): Promise<UsageStats> {
  const { data } = await api.get('/audit/stats')
  return data
}
