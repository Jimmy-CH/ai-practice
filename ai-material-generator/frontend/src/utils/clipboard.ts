/** 剪贴板工具：兼容非安全上下文（HTTP 部署）。

 * navigator.clipboard 仅在 secure context（HTTPS / localhost）存在，
 * 内网 HTTP 部署时为 undefined，必须降级到 execCommand('copy')。
 */

export async function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // 权限被拒等场景，继续走降级路径
    }
  }
  return copyViaExecCommand(text)
}

function copyViaExecCommand(text: string): boolean {
  const textarea = document.createElement('textarea')
  textarea.value = text
  // 移出可视区域避免页面滚动跳动；部分浏览器要求元素在 DOM 内才能选中
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '0'
  textarea.setAttribute('readonly', '')
  document.body.appendChild(textarea)
  const active = document.activeElement as HTMLElement | null
  textarea.select()
  textarea.setSelectionRange(0, text.length)
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(textarea)
  active?.focus()
  return ok
}
