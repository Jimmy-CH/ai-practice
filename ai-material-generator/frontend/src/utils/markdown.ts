import { marked } from 'marked'

export function renderMarkdown(md: string): string {
  return marked(md) as string
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return '-'
  const normalized = value.endsWith('Z') || value.includes('+') ? value : value + 'Z'
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
