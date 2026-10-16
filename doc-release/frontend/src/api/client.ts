import axios from 'axios'
import type { Preview, Refs, Repo, RunDetail, RunList, Scenario } from '@/types'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

export async function getRepos(): Promise<Repo[]> {
  return (await http.get('/repos')).data
}

export async function createRepo(path: string, name?: string): Promise<Repo> {
  return (await http.post('/repos', { path, name })).data
}

export async function deleteRepo(id: number): Promise<void> {
  await http.delete(`/repos/${id}`)
}

export async function getRefs(repoId: number): Promise<Refs> {
  return (await http.get(`/repos/${repoId}/refs`)).data
}

export async function getScenarios(repoId: number): Promise<Scenario[]> {
  return (await http.get(`/repos/${repoId}/scenarios`)).data
}

export async function getPreview(repoId: number, base: string, head: string): Promise<Preview> {
  return (await http.get(`/repos/${repoId}/preview`, { params: { base, head } })).data
}

export interface RunCreatePayload {
  repo_id: number
  base_ref: string
  head_ref: string
  version_label?: string
  tone?: string
  mask?: boolean
}

export async function createRun(payload: RunCreatePayload): Promise<RunDetail> {
  return (await http.post('/runs', payload)).data
}

export async function getRuns(limit = 20, offset = 0): Promise<RunList> {
  return (await http.get('/runs', { params: { limit, offset } })).data
}

export async function getRun(runId: string): Promise<RunDetail> {
  return (await http.get(`/runs/${runId}`)).data
}

export async function cancelRun(runId: string): Promise<void> {
  await http.post(`/runs/${runId}/cancel`)
}

export async function deleteRun(runId: string): Promise<void> {
  await http.delete(`/runs/${runId}`)
}

export async function getArtifactText(runId: string, kind: string, tone: string, mask: boolean): Promise<string> {
  const resp = await http.get(`/runs/${runId}/artifacts/${kind}`, {
    params: { tone, mask },
    responseType: 'text',
    transformResponse: [(data: string) => data],
  })
  return resp.data as string
}

export function artifactDownloadUrl(runId: string, kind: string, tone: string, mask: boolean): string {
  return `/api/runs/${runId}/artifacts/${kind}/download?tone=${tone}&mask=${mask}`
}

export function extractError(err: unknown): string {
  const e = err as { response?: { data?: { detail?: unknown } }; message?: string }
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => (d as { msg?: string }).msg || '').join('；')
  }
  return e?.message || '请求失败'
}
