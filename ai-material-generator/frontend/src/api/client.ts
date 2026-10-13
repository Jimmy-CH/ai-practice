import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

export interface AnalysisResult {
  title: string
  '新增功能': string[]
  '变更与优化': string[]
  '注意事项': string[]
  '风险提示': string[]
}

export interface Material {
  title: string
  content: string
  audience: string
  material_type: string
  meta: {
    audience: string
    material_type: string
    generator: string
  }
}

export async function parseDocument(title: string, content: string, file?: File): Promise<AnalysisResult> {
  const form = new FormData()
  form.append('title', title)
  if (file) {
    form.append('file', file)
  } else {
    form.append('content', content)
  }
  const response = await api.post('/parse', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function generateMaterial(
  title: string,
  analysis: AnalysisResult,
  audience: string,
  materialType: string,
): Promise<Material> {
  const response = await api.post('/generate', {
    title,
    analysis,
    audience,
    material_type: materialType,
  })
  return response.data
}

export async function generateAllMaterials(
  title: string,
  analysis: AnalysisResult,
  audience: string,
): Promise<{ audience: string; materials: Material[] }> {
  const response = await api.post('/generate-all', {
    title,
    analysis,
    audience,
  })
  return response.data
}

export default api
