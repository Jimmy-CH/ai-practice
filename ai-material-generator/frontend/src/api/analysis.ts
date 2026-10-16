import api from './client'
import type { AnalysisResult } from './client'

export interface AnalysisUpdatePayload {
  new_features: string[]
  changes: string[]
  notices: string[]
  risks: string[]
}

export async function getAnalysis(sourceTitle: string): Promise<AnalysisResult> {
  const response = await api.get(`/analyses/${encodeURIComponent(sourceTitle)}`)
  const data = response.data
  return {
    analysis_id: data.id,
    title: sourceTitle,
    '新增功能': data['新增功能'],
    '变更与优化': data['变更与优化'],
    '注意事项': data['注意事项'],
    '风险提示': data['风险提示'],
  }
}

export async function updateAnalysis(
  analysisId: number,
  payload: AnalysisUpdatePayload,
): Promise<AnalysisResult> {
  const response = await api.put(`/analyses/${analysisId}`, payload)
  const data = response.data
  return {
    analysis_id: data.id,
    title: data.source_title,
    '新增功能': data['新增功能'],
    '变更与优化': data['变更与优化'],
    '注意事项': data['注意事项'],
    '风险提示': data['风险提示'],
  }
}
