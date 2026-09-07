import api from './auth'

export interface ReportOut {
  id: number
  name: string
  question: string
  schedule_type: string
  schedule_time: string
  last_result: string
  last_run_at: string | null
  is_active: boolean
  created_at: string
}

export async function getReports(): Promise<ReportOut[]> {
  const { data } = await api.get('/reports/')
  return data
}

export async function createReport(
  name: string, question: string, scheduleType = 'daily', scheduleTime = '09:00',
): Promise<ReportOut> {
  const { data } = await api.post('/reports/', {
    name, question, schedule_type: scheduleType, schedule_time: scheduleTime,
  })
  return data
}

export async function toggleReport(reportId: number): Promise<ReportOut> {
  const { data } = await api.put(`/reports/${reportId}/toggle`)
  return data
}

export async function deleteReport(reportId: number): Promise<void> {
  await api.delete(`/reports/${reportId}`)
}

export async function runReport(reportId: number): Promise<{ result: string }> {
  const { data } = await api.post(`/reports/${reportId}/run`)
  return data
}
