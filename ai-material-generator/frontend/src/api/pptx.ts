import client from './client'

export interface TrainingPptxPayload {
  title: string
  content: string
  audience: string
  source_title: string
}

export function buildTrainingPptx(payload: TrainingPptxPayload) {
  // 接口直接返回文件流，需以 blob 接收；错误体同样是 blob，调用方需单独解析
  return client.post('/pptx/training-outline', payload, { responseType: 'blob' })
}
