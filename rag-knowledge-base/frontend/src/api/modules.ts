import http from './index'
import type { AskResponse, UploadResponse, HealthResponse } from '@/types'

export const chatApi = {
  async ask(question: string, topK?: number): Promise<AskResponse> {
    const { data } = await http.post<AskResponse>('/v1/ask', {
      question,
      top_k: topK,
    })
    return data
  },
}

export const documentApi = {
  async upload(file: File): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await http.post<UploadResponse>('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },
}

export const healthApi = {
  async check(): Promise<HealthResponse> {
    const { data } = await http.get<HealthResponse>('/health')
    return data
  },
}
