import DOMPurify from 'dompurify'
import { marked, type Tokens } from 'marked'

/** 解析带 BOM 的 CSV 文本为二维数组，支持引号转义与字段内逗号。 */
export function parseCsv(text: string): string[][] {
  const src = text.replace(/^\uFEFF/, '')
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  for (let i = 0; i < src.length; i += 1) {
    const ch = src[i]
    if (quoted) {
      if (ch === '"') {
        if (src[i + 1] === '"') {
          field += '"'
          i += 1
        } else {
          quoted = false
        }
      } else {
        field += ch
      }
    } else if (ch === '"') {
      quoted = true
    } else if (ch === ',') {
      row.push(field)
      field = ''
    } else if (ch === '\n') {
      row.push(field)
      field = ''
      rows.push(row)
      row = []
    } else if (ch !== '\r') {
      field += ch
    }
  }
  if (field !== '' || row.length) {
    row.push(field)
    rows.push(row)
  }
  return rows.filter((r) => r.some((c) => c.trim() !== ''))
}

/** JSON 文本格式化；解析失败时原样返回。 */
export function formatJson(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

/** 基础 HTML 转义：mermaid 源码作为文本节点交给前端绘图，避免被当作标签解析。 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** Markdown 渲染为 HTML（经 DOMPurify 净化，防产物内嵌脚本注入）。
 * ```mermaid 代码块输出为待绘制容器；其余代码块沿用 marked 默认渲染。 */
export function renderMarkdown(md: string): string {
  const renderer = new marked.Renderer()
  const defaultCode = renderer.code.bind(renderer)
  renderer.code = (token: Tokens.Code) => {
    if ((token.lang || '').trim().toLowerCase() === 'mermaid') {
      return `<div class="mermaid">${escapeHtml(token.text)}</div>`
    }
    return defaultCode(token)
  }
  return DOMPurify.sanitize(marked.parse(md, { renderer }) as string)
}
