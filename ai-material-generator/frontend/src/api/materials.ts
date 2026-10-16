import client from './client'

export interface Material {
  id: number
  title: string
  content: string
  material_type: string
  audience: string
  status: string
  review_comment: string | null
  reviewed_by: number | null
  reviewed_at: string | null
  reviewer_username: string | null
  created_at: string
  updated_at: string
}

export function listMaterials(status?: string) {
  return client.get('/materials', { params: status ? { status } : {} })
}

export function getMaterial(id: number) {
  return client.get(`/materials/${id}`)
}

export function createMaterial(data: Partial<Material>) {
  return client.post('/materials', data)
}

export function updateMaterial(id: number, data: Partial<Material>) {
  return client.put(`/materials/${id}`, data)
}

export function submitMaterial(id: number) {
  return client.post(`/materials/${id}/submit`)
}

export function deleteMaterial(id: number) {
  return client.delete(`/materials/${id}`)
}

export function reviewMaterial(id: number, action: 'approve' | 'reject', comment: string = '') {
  return client.post(`/materials/${id}/reviews`, { action, comment })
}

export function listPending() {
  return client.get('/materials/pending')
}

export function listApproved() {
  return client.get('/materials/approved')
}

export function downloadMaterial(id: number) {
  return client.get(`/materials/${id}/download`, { responseType: 'blob' })
}

export function saveFromGeneration(data: {
  title: string
  content: string
  material_type: string
  audience: string
  source_title: string
  analysis: string
}) {
  return client.post('/materials/from-generation', data)
}
