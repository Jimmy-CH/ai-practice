import client from './client'

export interface PosterImage {
  id: number
  owner_id: number
  source_title: string
  audience: string
  prompt: string
  file_size: number
  image_url: string
  created_at: string
}

export function refinePosterPrompt(scriptContent: string) {
  return client.post('/posters/prompt', { script_content: scriptContent })
}

export function createPosterImage(data: {
  source_title: string
  audience: string
  prompt: string
}) {
  return client.post('/posters/images', data)
}

export function listPosterImages(sourceTitle: string, audience: string) {
  return client.get('/posters/images', { params: { source_title: sourceTitle, audience } })
}

export function fetchPosterImageFile(id: number) {
  // 文件接口需带 Authorization，<img> 直连不可行，调用方用 blob 转 object URL
  return client.get(`/posters/images/${id}/file`, { responseType: 'blob' })
}

export function deletePosterImage(id: number) {
  return client.delete(`/posters/images/${id}`)
}
