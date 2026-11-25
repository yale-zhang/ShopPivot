/** 状态 → 语义色的唯一映射。 */
import { zhCN, type Tone } from '../i18n/zh-CN'

const SUCCESS = new Set([
  'APPROVED',
  'SUCCEEDED',
  'INSTALLED',
  'ENABLED',
  'NORMAL',
  'ONLINE',
  'COMPLETED',
  'ACCEPTED',
  'VERIFIED',
])
const WARNING = new Set([
  'PENDING',
  'OPEN',
  'BUSY',
  'DEGRADED',
  'WARNING',
  'OVERDUE',
  'PARTIAL',
  'COMPENSATED',
])
const DANGER = new Set(['REJECTED', 'FAILED', 'BLOCKED', 'ERROR', 'OFFLINE'])
const NEUTRAL = new Set([
  'EXPIRED',
  'DISABLED',
  'CANCELLED',
  'SKIPPED',
  'UNKNOWN',
  'CLOSED',
  'IGNORED',
  'WITHDRAWN',
])
const INFO = new Set(['RUNNING', 'ASSIGNED', 'TODO-APPROVAL', 'TODO-EXCEPTION', 'INFO'])

export function toneForStatus(status: string | null | undefined): Tone {
  if (!status) return 'neutral'
  const code = status.toUpperCase()
  if (SUCCESS.has(code)) return 'success'
  if (WARNING.has(code)) return 'warning'
  if (DANGER.has(code)) return 'danger'
  if (NEUTRAL.has(code)) return 'neutral'
  if (INFO.has(code)) return 'info'
  return 'neutral'
}

export function labelForStatus(status: string | null | undefined): string {
  if (!status) return zhCN.common.unknown
  return zhCN.statusLabel[status] ?? status
}

export function labelForModuleState(state: string | null | undefined): string {
  if (!state) return zhCN.common.unknown
  return zhCN.p09.stateLabels[state] ?? labelForStatus(state)
}

export function labelForTodoType(type: string | null | undefined): string {
  if (!type) return zhCN.common.unknown
  return zhCN.todoType[type] ?? type
}

export function toneForTodoType(type: string | null | undefined): Tone {
  if (type === 'TODO-EXCEPTION') return 'danger'
  return 'info'
}
