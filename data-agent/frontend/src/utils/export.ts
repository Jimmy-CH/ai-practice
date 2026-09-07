import Papa from 'papaparse'

export function exportToCSV(data: string[][], filename: string) {
  if (!data.length) return
  const headers = data[0]
  const rows = data.slice(1)
  const csv = Papa.unparse({ fields: headers, data: rows })

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const now = new Date()
  const ts = now.toISOString().replace(/[:.]/g, '-').slice(0, 19)
  link.href = url
  link.download = `${filename}_${ts}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

// 从 Agent observation 步骤中解析表格数据
export function parseObservationTable(steps: { type: string; content: string }[]): string[][] | null {
  for (const step of steps) {
    if (step.type === 'observation' && step.content.includes(' | ')) {
      const lines = step.content.split('\n').filter(l => l.trim() && !l.startsWith('---'))
      return lines.map(line => line.split(' | ').map(cell => cell.trim()))
    }
  }
  return null
}
