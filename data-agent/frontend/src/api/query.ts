import { api } from './auth'

export interface SavedQueryOut {
  id: number
  name: string
  question: string
  is_favorite: boolean
  created_at: string
}

export async function getSavedQueries(): Promise<SavedQueryOut[]> {
  const { data } = await api.get('/queries/')
  return data.queries
}

export async function saveQuery(name: string, question: string, isFavorite = false): Promise<SavedQueryOut> {
  const { data } = await api.post('/queries/', { name, question, is_favorite: isFavorite })
  return data
}

export async function deleteSavedQuery(queryId: number): Promise<void> {
  await api.delete(`/queries/${queryId}`)
}

export async function toggleFavorite(queryId: number): Promise<{ is_favorite: boolean }> {
  const { data } = await api.put(`/queries/${queryId}/favorite`)
  return data
}
