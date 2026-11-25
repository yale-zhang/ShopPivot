/** 展示格式化：数值、时间、哈希、倒计时。不含中文文案。 */
import type { ReportCell } from '../api/types'

const dateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const shortDateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

function toDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatDateTime(value: string | null | undefined): string {
  const date = toDate(value)
  return date ? dateTimeFormatter.format(date) : ''
}

export function formatShortDateTime(value: string | null | undefined): string {
  const date = toDate(value)
  return date ? shortDateTimeFormatter.format(date) : ''
}

export function formatDate(value: string | null | undefined): string {
  const date = toDate(value)
  return date ? dateFormatter.format(date) : ''
}

export function formatClock(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return ''
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

/** 倒计时格式固定 mm:ss；超过 60 分钟时分钟位继续累加。 */
export function formatCountdown(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return ''
  const total = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(total / 60)
  const rest = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

/** SLA 倒计时：不足 1 小时用 mm:ss，否则用 hh:mm:ss。 */
export function formatSlaCountdown(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return ''
  const total = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const rest = total % 60
  if (hours > 0) {
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
  }
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

/** `2026-11-25` → `11-25`；无法解析时原样返回。 */
export function formatMonthDay(value: string | null | undefined): string {
  if (!value) return ''
  const matched = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  return matched ? `${matched[2]}-${matched[3]}` : value
}

export function truncateMiddle(value: string, head = 12, tail = 4): string {
  if (!value) return ''
  if (value.length <= head + tail + 1) return value
  return `${value.slice(0, head)}…${value.slice(-tail)}`
}

export function truncateHead(value: string, length = 12): string {
  if (!value) return ''
  return value.length <= length ? value : `${value.slice(0, length)}…`
}

export function isNullCell(cell: ReportCell | null | undefined): boolean {
  if (!cell) return true
  return cell.raw === null || cell.null_reason !== null
}

export interface CellView {
  text: string
  isNull: boolean
  reason: string
}

/** 空值不得显示 0；统一以「不适用」呈现，原因作为附注。 */
export function cellView(cell: ReportCell | null | undefined, notApplicable: string): CellView {
  if (isNullCell(cell)) {
    return {
      text: notApplicable,
      isNull: true,
      reason: cell?.null_reason ?? '',
    }
  }
  return { text: cell?.value ?? notApplicable, isNull: false, reason: '' }
}

export function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

/** 从 `/change-orders/<id>` 提取变更单号，避免把路由片段带入 API。 */
export function changeOrderIdFromHref(href: string | null | undefined): string | null {
  if (!href) return null
  const matched = /\/change-orders\/([^/?#]+)/.exec(href)
  if (matched?.[1]) return decodeURIComponent(matched[1])
  return null
}

export function formatNumber(value: number, precision = 0): string {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  }).format(value)
}

export function formatByteSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** exponent).toFixed(exponent === 0 ? 0 : 1)} ${units[exponent]}`
}
