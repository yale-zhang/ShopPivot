/** 后端 API 客户端：鉴权、错误封装、401 统一处理。 */
import { zhCN } from '../i18n/zh-CN'
import type {
  AdsSummaryResponse,
  ApprovalHistoryResponse,
  AuditResponse,
  CardsResponse,
  ChangeOrderPayload,
  ChangeOrderTransferResponse,
  ContextsResponse,
  CreateWritePlanRequest,
  ErrorEnvelope,
  EvidencePayload,
  ExceptionsResponse,
  InventoryReconciliationResponse,
  LoginResponse,
  MetricCardPayload,
  MetricCardsResponse,
  MetricDiffResponse,
  MetricReleaseSummary,
  ModuleActionResponse,
  ModulesResponse,
  NavResponse,
  NotificationTemplatesResponse,
  PlatformPriceListResponse,
  ReportPayload,
  ReviewAssignResponse,
  ReviewCloseResponse,
  ReviewSummaryResponse,
  ReviewTicketsResponse,
  RolesResponse,
  RunDetailPayload,
  SuggestionActionResponse,
  SubscriptionCreatePayload,
  SubscriptionMutationResponse,
  SubscriptionsResponse,
  TodosResponse,
  WorkerRegisterResponse,
  WorkersResponse,
  WritePlanApproveResponse,
  WritePlanCreateResponse,
  WritePlanMutationResponse,
} from './types'

export const TOKEN_KEY = 'shoppivot.token'
export const ROLE_KEY = 'shoppivot.role'
export const USERNAME_KEY = 'shoppivot.username'
export const DISPLAY_NAME_KEY = 'shoppivot.display_name'
export const SHOPS_KEY = 'shoppivot.shops'

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1'

export class ApiError extends Error {
  readonly code: string
  readonly layer: string
  readonly userMessage: string
  readonly retryable: boolean
  readonly status: number
  readonly details: Record<string, unknown>

  constructor(options: {
    code: string
    layer: string
    message?: string
    userMessage: string
    retryable?: boolean
    status?: number
    details?: Record<string, unknown>
  }) {
    super(options.message ?? options.userMessage)
    this.name = 'ApiError'
    this.code = options.code
    this.layer = options.layer
    this.userMessage = options.userMessage
    this.retryable = options.retryable ?? false
    this.status = options.status ?? 0
    this.details = options.details ?? {}
  }
}

type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? ''
  } catch {
    return ''
  }
}

export function clearAuthStorage(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(ROLE_KEY)
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(DISPLAY_NAME_KEY)
    localStorage.removeItem(SHOPS_KEY)
  } catch {
    /* 本地存储不可用时忽略 */
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  auth?: boolean
  query?: Record<string, string | number | boolean | null | undefined>
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const base = API_BASE.replace(/\/$/, '')
  let url = `${base}${path}`
  if (query) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        params.set(key, String(value))
      }
    }
    const serialized = params.toString()
    if (serialized) url += `?${serialized}`
  }
  return url
}

function fallbackMessage(status: number): string {
  if (status === 401) return zhCN.errors.unauthorized
  if (status === 403) return zhCN.errors.forbidden
  return zhCN.errors.unknown
}

async function toApiError(response: Response): Promise<ApiError> {
  let envelope: Partial<ErrorEnvelope> = {}
  try {
    envelope = (await response.json()) as Partial<ErrorEnvelope>
  } catch {
    envelope = {}
  }
  // Vite 代理在后端未启动时返回 500/502 且不是我们的错误信封：
  // 这属于“服务不可达”，不能显示成泛化的“请求处理失败”。
  const isEnvelope = typeof envelope.code === 'string' && typeof envelope.layer === 'string'
  if (!isEnvelope && response.status >= 500) {
    return new ApiError({
      code: 'E008',
      layer: 'SYS',
      userMessage: zhCN.errors.unreachable,
      retryable: true,
      status: response.status,
    })
  }
  return new ApiError({
    code: envelope.code ?? 'E000',
    layer: envelope.layer ?? 'SYS',
    message: envelope.message ?? envelope.user_message ?? response.statusText,
    userMessage: envelope.user_message ?? fallbackMessage(response.status),
    retryable: envelope.retryable ?? false,
    status: response.status,
    details: envelope.details ?? {},
  })
}

async function performFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  const { body, auth = true, query, headers: extraHeaders, ...init } = options
  const headers = new Headers(extraHeaders)
  if (body !== undefined) headers.set('Content-Type', 'application/json')
  const token = getToken()
  if (auth && token) headers.set('Authorization', `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      ...init,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError({
      code: 'E000',
      layer: 'SYS',
      userMessage: zhCN.errors.unreachable,
      retryable: true,
      status: 0,
    })
  }

  if (response.status === 401 && auth) {
    clearAuthStorage()
    unauthorizedHandler?.()
    throw await toApiError(response)
  }
  if (!response.ok) {
    throw await toApiError(response)
  }
  return response
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await performFetch(path, options)
  if (response.status === 204) return undefined as T
  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError({
      code: 'E000',
      layer: 'UI',
      userMessage: zhCN.errors.parse,
      status: response.status,
    })
  }
}

/* ------------------------------------------------------------------ */
/* 接口                                                                */
/* ------------------------------------------------------------------ */

export function login(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    auth: false,
    body: { username, password },
  })
}

export function fetchContexts(): Promise<ContextsResponse> {
  return request<ContextsResponse>('/workbench/contexts')
}

export function fetchNav(): Promise<NavResponse> {
  return request<NavResponse>('/workbench/nav')
}

export function fetchCards(page: string): Promise<CardsResponse> {
  return request<CardsResponse>('/workbench/cards', { query: { page } })
}

export function fetchLatestReport(params: {
  platform: string
  shopId: string
  window?: string
  metricVersion?: string
}): Promise<ReportPayload> {
  return request<ReportPayload>('/reports/latest', {
    query: {
      platform: params.platform,
      shop_id: params.shopId,
      window: params.window,
      metric_version: params.metricVersion,
    },
  })
}

export function fetchReport(reportId: string): Promise<ReportPayload> {
  return request<ReportPayload>(`/reports/${encodeURIComponent(reportId)}`)
}

export interface ExportedFile {
  blob: Blob
  filename: string
}

export async function exportReport(reportId: string): Promise<ExportedFile> {
  const response = await performFetch(`/reports/${encodeURIComponent(reportId)}/export`)
  const disposition = response.headers.get('content-disposition') ?? ''
  const matched = /filename="?([^";]+)"?/i.exec(disposition)
  const blob = await response.blob()
  return {
    blob,
    filename: matched?.[1] ?? `${reportId}.xlsx`,
  }
}

export function fetchMetricCard(metricCode: string): Promise<MetricCardPayload> {
  return request<MetricCardPayload>(`/metric-cards/${encodeURIComponent(metricCode)}`)
}

export function fetchRun(runId: string): Promise<RunDetailPayload> {
  return request<RunDetailPayload>(`/runs/${encodeURIComponent(runId)}`)
}

export function fetchEvidence(runId: string, payloadId: number | string): Promise<EvidencePayload> {
  return request<EvidencePayload>(
    `/runs/${encodeURIComponent(runId)}/evidence/${encodeURIComponent(String(payloadId))}`,
  )
}

export function fetchTodos(): Promise<TodosResponse> {
  return request<TodosResponse>('/todos')
}

export function fetchChangeOrder(changeOrderNo: string): Promise<ChangeOrderPayload> {
  return request<ChangeOrderPayload>(`/change-orders/${encodeURIComponent(changeOrderNo)}`)
}

/* ------------------------------------------------------------------ */
/* M2 · P06 变更单审批动作                                             */
/* ------------------------------------------------------------------ */

export function approveWritePlan(
  planId: string,
  reason = '',
): Promise<WritePlanApproveResponse> {
  return request<WritePlanApproveResponse>(
    `/write-plans/${encodeURIComponent(planId)}/approve`,
    { method: 'POST', body: { reason } },
  )
}

export function rejectWritePlan(
  planId: string,
  reason: string,
): Promise<WritePlanMutationResponse> {
  return request<WritePlanMutationResponse>(
    `/write-plans/${encodeURIComponent(planId)}/reject`,
    { method: 'POST', body: { reason } },
  )
}

export function withdrawWritePlan(
  planId: string,
  reason = '',
): Promise<WritePlanMutationResponse> {
  return request<WritePlanMutationResponse>(
    `/write-plans/${encodeURIComponent(planId)}/withdraw`,
    { method: 'POST', body: { reason } },
  )
}

export function compensateWritePlan(
  planId: string,
  reason: string,
): Promise<WritePlanMutationResponse> {
  return request<WritePlanMutationResponse>(
    `/write-plans/${encodeURIComponent(planId)}/compensate`,
    { method: 'POST', body: { reason } },
  )
}

/** 转交审批任务：不改变计划内容，只更换审批人并重算 SLA。 */
export function transferChangeOrder(
  taskId: string,
  approver: string,
  reason = '',
): Promise<ChangeOrderTransferResponse> {
  return request<ChangeOrderTransferResponse>(
    `/change-orders/${encodeURIComponent(taskId)}/transfer`,
    { method: 'POST', body: { approver, reason } },
  )
}

/* ------------------------------------------------------------------ */
/* M2 · P05 新建变更单                                                 */
/* ------------------------------------------------------------------ */

export function fetchPlatformPriceList(): Promise<PlatformPriceListResponse> {
  return request<PlatformPriceListResponse>('/platform/price-list')
}

export function createWritePlan(
  payload: CreateWritePlanRequest,
): Promise<WritePlanCreateResponse> {
  return request<WritePlanCreateResponse>('/write-plans', { method: 'POST', body: payload })
}

/* ------------------------------------------------------------------ */
/* M2 · P07 审批记录与审计                                             */
/* ------------------------------------------------------------------ */

export function fetchApprovalHistory(
  params: {
    limit?: number
    status?: string
    actionCode?: string
    approver?: string
  } = {},
): Promise<ApprovalHistoryResponse> {
  return request<ApprovalHistoryResponse>('/approvals/history', {
    query: {
      limit: params.limit ?? 100,
      status: params.status,
      action_code: params.actionCode,
      approver: params.approver,
    },
  })
}

/** 按对象反查审计时间线；object_id 优先用 plan_id，缺失时退回 task_id。 */
export function fetchAudit(params: {
  objectId: string
  limit?: number
}): Promise<AuditResponse> {
  return request<AuditResponse>('/audit', {
    query: { object_id: params.objectId, limit: params.limit ?? 100 },
  })
}

export function fetchModules(): Promise<ModulesResponse> {
  return request<ModulesResponse>('/modules')
}

export function disableModule(name: string): Promise<ModuleActionResponse> {
  return request<ModuleActionResponse>(`/modules/${encodeURIComponent(name)}/disable`, {
    method: 'POST',
  })
}

export function enableModule(name: string): Promise<ModuleActionResponse> {
  return request<ModuleActionResponse>(`/modules/${encodeURIComponent(name)}/enable`, {
    method: 'POST',
  })
}

export function fetchWorkers(): Promise<WorkersResponse> {
  return request<WorkersResponse>('/workers')
}

/* ------------------------------------------------------------------ */
/* M1 · P02 评价与口碑                                                 */
/* ------------------------------------------------------------------ */

export function fetchReviewTickets(
  status?: 'OPEN' | 'ASSIGNED' | 'CLOSED',
): Promise<ReviewTicketsResponse> {
  return request<ReviewTicketsResponse>('/reviews/tickets', { query: { status } })
}

export function fetchReviewSummary(): Promise<ReviewSummaryResponse> {
  return request<ReviewSummaryResponse>('/reviews/summary')
}

export function assignReviewTicket(
  ticketId: string,
  assignee: string,
): Promise<ReviewAssignResponse> {
  return request<ReviewAssignResponse>(
    `/reviews/tickets/${encodeURIComponent(ticketId)}/assign`,
    { method: 'POST', body: { assignee } },
  )
}

export function closeReviewTicket(
  ticketId: string,
  resolution: string,
): Promise<ReviewCloseResponse> {
  return request<ReviewCloseResponse>(
    `/reviews/tickets/${encodeURIComponent(ticketId)}/close`,
    { method: 'POST', body: { resolution } },
  )
}

/* ------------------------------------------------------------------ */
/* M1 · P03 库存与补货                                                 */
/* ------------------------------------------------------------------ */

export function fetchInventoryReconciliation(
  runId?: string | null,
): Promise<InventoryReconciliationResponse> {
  return request<InventoryReconciliationResponse>('/inventory/reconciliation', {
    query: { run_id: runId },
  })
}

export function acceptInventorySuggestion(
  suggestionId: string,
  note = '',
): Promise<SuggestionActionResponse> {
  return request<SuggestionActionResponse>(
    `/inventory/suggestions/${encodeURIComponent(suggestionId)}/accept`,
    { method: 'POST', body: { note } },
  )
}

export function ignoreInventorySuggestion(
  suggestionId: string,
  note = '',
): Promise<SuggestionActionResponse> {
  return request<SuggestionActionResponse>(
    `/inventory/suggestions/${encodeURIComponent(suggestionId)}/ignore`,
    { method: 'POST', body: { note } },
  )
}

/* ------------------------------------------------------------------ */
/* P04 活动与投放                                                      */
/* ------------------------------------------------------------------ */

export function fetchAdsSummary(runId?: string | null): Promise<AdsSummaryResponse> {
  return request<AdsSummaryResponse>('/ads/summary', { query: { run_id: runId } })
}

/* ------------------------------------------------------------------ */
/* M1 · P10 口径与数据合同                                             */
/* ------------------------------------------------------------------ */

export function fetchMetricCards(): Promise<MetricCardsResponse> {
  return request<MetricCardsResponse>('/metric-cards')
}

export function fetchMetricDiff(
  metricCode: string,
  from?: string,
  to?: string,
): Promise<MetricDiffResponse> {
  return request<MetricDiffResponse>(`/metric-cards/${encodeURIComponent(metricCode)}/diff`, {
    query: { from, to },
  })
}

export function releaseMetricCard(metricCode: string): Promise<MetricReleaseSummary> {
  return request<MetricReleaseSummary>(
    `/metric-cards/${encodeURIComponent(metricCode)}/release`,
    { method: 'POST' },
  )
}

export function fetchMetricRelease(metricCode: string): Promise<MetricReleaseSummary> {
  return request<MetricReleaseSummary>(
    `/metric-cards/${encodeURIComponent(metricCode)}/release`,
  )
}

/* ------------------------------------------------------------------ */
/* M1 · P11 机器人与日志                                               */
/* ------------------------------------------------------------------ */

export function registerDemoWorker(): Promise<WorkerRegisterResponse> {
  return request<WorkerRegisterResponse>('/worker/register-demo', { method: 'POST' })
}

export function fetchExceptions(limit = 100): Promise<ExceptionsResponse> {
  return request<ExceptionsResponse>('/exceptions', { query: { limit } })
}

/* ------------------------------------------------------------------ */
/* M1 · P12 权限与订阅                                                 */
/* ------------------------------------------------------------------ */

export function fetchIdentityRoles(): Promise<RolesResponse> {
  return request<RolesResponse>('/identity/roles')
}

export function fetchSubscriptions(): Promise<SubscriptionsResponse> {
  return request<SubscriptionsResponse>('/subscriptions')
}

export function createSubscription(
  payload: SubscriptionCreatePayload,
): Promise<SubscriptionMutationResponse> {
  return request<SubscriptionMutationResponse>('/subscriptions', {
    method: 'POST',
    body: payload,
  })
}

export function deleteSubscription(id: number): Promise<SubscriptionMutationResponse> {
  return request<SubscriptionMutationResponse>(`/subscriptions/${encodeURIComponent(String(id))}`, {
    method: 'DELETE',
  })
}

export function fetchNotificationTemplates(): Promise<NotificationTemplatesResponse> {
  return request<NotificationTemplatesResponse>('/notifications/templates')
}
