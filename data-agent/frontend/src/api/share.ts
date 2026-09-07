import { api } from './auth'

export interface ShareQueryOut {
  token: string
  url: string
  expires_at: string | null
}

export interface SharedQueryDetail {
  question: string
  answer: string
  steps: any[]
  chart_data: any | null
  created_at: string
  expires_at: string | null
}

export async function createShare(
  question: string,
  answer: string,
  steps: any[] = [],
  chartData: any = null,
  expiresHours?: number,
): Promise<ShareQueryOut> {
  const { data } = await api.post('/share/', {
    question, answer, steps, chart_data: chartData, expires_hours: expiresHours,
  })
  return data
}

export async function getShared(token: string): Promise<SharedQueryDetail> {
  const { data } = await api.get(`/share/${token}`)
  return data
}

export async function listShares(): Promise<any[]> {
  const { data } = await api.get('/share/')
  return data
}
