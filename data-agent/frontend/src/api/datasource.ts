import { api } from './auth'

export interface ColumnInfo {
  column_name: string
  column_type: string
  description: string
}

export interface DataSourceOut {
  id: number
  table_name: string
  original_filename: string
  description: string
  row_count: number
  columns: ColumnInfo[]
  created_at: string
}

export interface DataSourceListOut {
  sources: DataSourceOut[]
}

export async function getDataSources(): Promise<DataSourceOut[]> {
  const { data } = await api.get<DataSourceListOut>('/datasource/')
  return data.sources
}

export async function uploadDataSource(file: File): Promise<DataSourceOut> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post<DataSourceOut>('/datasource/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function updateDataSource(
  sourceId: number,
  description: string,
  columnDescriptions: { column_name: string; description: string }[],
): Promise<DataSourceOut> {
  const { data } = await api.put<DataSourceOut>(`/datasource/${sourceId}`, {
    description,
    column_descriptions: columnDescriptions,
  })
  return data
}

export async function deleteDataSource(sourceId: number): Promise<void> {
  await api.delete(`/datasource/${sourceId}`)
}
