/** 时间展示：后端下发带 Z 的 UTC 时间，页面统一转换为本地时间。 */

const WITH_TZ = /([zZ]|[+-]\d{2}:?\d{2})$/

/** 老数据可能没有时区后缀，按 UTC 解释，避免被当成已本地化时间再偏一次。 */
function toDate(iso: string): Date | null {
  const normalized = WITH_TZ.test(iso) ? iso : `${iso}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  const date = toDate(iso)
  if (!date) return iso.replace('T', ' ').slice(0, 19)
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}

export function formatDuration(
  startIso: string | null | undefined,
  endIso: string | null | undefined,
): string {
  if (!startIso || !endIso) return '-'
  const start = toDate(startIso)
  const end = toDate(endIso)
  if (!start || !end) return '-'
  const ms = end.getTime() - start.getTime()
  if (!Number.isFinite(ms) || ms < 0) return '-'
  if (ms === 0) return '<1s'
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}
