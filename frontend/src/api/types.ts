/** 与 ShopPivot 后端 `/api/v1` 对齐的响应类型。 */

export interface ShopRef {
  platform: string
  shop_id: string
}

export interface ContextsResponse {
  platforms: string[]
  shops: ShopRef[]
  windows: string[]
  metric_versions: string[]
  role: string
  readonly: boolean
  platform_gate_max: string
  default: {
    platform: string
    shop_id: string
    window: string
  }
}

export interface NavPage {
  page_id: string
  menu: string
  title: string
  roles: string[]
  available: boolean
  card_ids: string[]
}

export interface NavResponse {
  pages: NavPage[]
  readonly: boolean
}

export interface WorkbenchCard {
  card_id: string
  page_id: string
  module: string
  title: string
  slot: string
  data_endpoint: string
  empty_state_copy: string
  order: number
}

export interface CardsResponse {
  page_id: string
  cards: WorkbenchCard[]
  readonly: boolean
}

export type Additivity = 'ADDITIVE' | 'RATIO' | 'NON_ADDITIVE'

export interface ReportColumn {
  key: string
  label: string
  unit: string
  precision: number
  additivity: Additivity | string
  additivity_label: string
  metric_version: string
  display_order: number
  source: string
  drill: string
  null_policy: string
}

export interface ReportCell {
  value: string
  raw: string | null
  null_reason: string | null
  metric_code: string
}

export interface ReportRow {
  stat_date: string
  cells: Record<string, ReportCell>
}

export interface ReportAlert {
  metric_code: string
  threshold: number
  value: string
  message: string
}

export interface ReportWindow {
  start: string
  end: string
}

export interface ReportPayload {
  report_id: string | null
  run_id: string | null
  platform: string
  shop_id: string
  window: ReportWindow | null
  window_label: string
  metric_version: string
  watermark: string
  channel: string | null
  channel_label: string
  generated_at: string | null
  data_state: string
  empty_copy: string
  columns: ReportColumn[]
  rows: ReportRow[]
  alerts: ReportAlert[]
  readonly: boolean
  drill?: string
  config_snapshot_hash?: string
  gate_level_max?: string
}

export interface InspectedValue {
  value: string | null
  null_reason: string | null
  stat_date: string
}

export interface MetricCardCompute {
  formula: string
  denominator: string | null
  unit: string
  precision: number
  additivity: Additivity | string
  null_policy: string
  source_mapping: string
}

export interface MetricCardQuality {
  quality_tests: string[]
  release_gate_passed: boolean
}

export interface MetricCardEvidence {
  probe_sql_template: string
  last_inspected_value: InspectedValue | null
  ods_refs: string[]
  run_id: string | null
}

export interface MetricCardPayload {
  id: string
  name: string
  metric_code: string
  version: string
  status: string
  domain: string
  effective_from: string
  breaking_change: boolean
  business_question: string
  concept_uri: string
  synonyms: string[]
  display_name: string
  compute: MetricCardCompute
  quality: MetricCardQuality
  evidence: MetricCardEvidence
  card: unknown
  readonly: boolean
}

export type RunNodeStatus = string

export interface RunNode {
  node_id: string
  status: RunNodeStatus
  cost_ms: number | null
  channel: string | null
  err_code: string | null
  err_layer: string | null
  payload_digest: string | null
}

export interface RunOdsItem {
  id: number
  dataset: string
  channel: string
  payload_hash: string
  record_count: number
  fetched_at: string
}

export interface RunReportRef {
  report_id: string
  metric_version: string
  artifact_ref: string
  generated_at: string
}

export interface RunDetailPayload {
  run_id: string
  app_id: string
  scene: string
  platform: string
  shop_id: string
  window: ReportWindow
  status: string
  gate_level_max: string
  started_at: string | null
  ended_at: string | null
  err_code: string | null
  err_layer: string | null
  config_snapshot_hash: string
  config_snapshot: Record<string, unknown>
  nodes: RunNode[]
  ods: RunOdsItem[]
  reports: RunReportRef[]
  exceptions: Array<Record<string, unknown>>
}

export interface EvidencePayload {
  id: number
  run_id: string
  dataset: string
  channel: string
  payload_hash: string
  record_count: number
  fetched_at: string
  masked: boolean
  masked_copy: string
  payload: unknown
}

export interface TodoItem {
  todo_id: string
  type: 'TODO-APPROVAL' | 'TODO-EXCEPTION' | string
  title: string
  status: string
  gate_level: string | null
  sla_expires_at: string | null
  remaining_seconds: number | null
  overdue: boolean
  href: string | null
  module: string
  created_at: string | null
}

export interface TodosResponse {
  items: TodoItem[]
  counts: Record<string, number>
  readonly: boolean
}

export interface ChangeOrderHeader {
  scene: string
  platform: string
  shop_id: string
  requested_by: string
  approver?: string | null
  created_at: string | null
  gate_level: string
  write_plan_hash: string
  metric_version: string | null
  snapshot_time: string | null
  schema_version: string
  sla_expires_at: string
}

export interface BeforeAfterRow {
  target: string
  field: string
  before: string
  after: string
  impact: string
}

export interface ChangeOrderEvidence {
  kind: string
  ref: string
  label: string
}

export interface TimelineEntry {
  state: string
  at: string | null
  label: string
}

export interface ChangeOrderExecution {
  execution_id: string
  status: 'VERIFIED' | 'FAILED' | 'RUNNING' | string
  before_shot: string | null
  after_shot: string | null
  verify_result: Record<string, unknown> | null
  err_code: string | null
  err_layer: string | null
  ended_at: string | null
}

export interface ChangeOrderPayload {
  change_order_no: string
  task_id: string
  plan_id: string | null
  status: string
  plan_status: string | null
  header: ChangeOrderHeader
  before_after: BeforeAfterRow[]
  impact_scope: string | null
  evidence: ChangeOrderEvidence[]
  rollback_plan: unknown
  evidence_complete: boolean
  readonly: boolean
  can_approve: boolean
  readonly_copy: string
  execution: ChangeOrderExecution | null
  result_timeline: TimelineEntry[]
}

export interface WritePlanSummary {
  plan_id: string
  action_code: string
  scene: string
  platform: string
  shop_id: string
  status: string
  summary: string
  impact_scope: string
  rollback_plan: string
  plan_hash: string
  rows: BeforeAfterRow[]
  evidence: ChangeOrderEvidence[]
  approval_task_id: string | null
  execution_id: string | null
  error_code: string | null
  error_layer: string | null
  created_at: string | null
  requested_by: string
}

export interface WritePlanExecutionResult {
  execution_id: string
  plan_id: string
  task_id: string
  status: string
  applied_rows: number
  before_shot: string
  after_shot: string
  verify_result: Record<string, unknown>
  details: Record<string, unknown>
  err_code: string | null
  err_layer: string | null
  started_at: string | null
  ended_at: string | null
}

export interface WritePlanApproveResponse {
  plan: WritePlanSummary
  execution: WritePlanExecutionResult | null
}

export interface WritePlanMutationResponse {
  plan: WritePlanSummary
}

export interface ChangeOrderTransferResponse {
  task_id: string
  status: string
  approver: string
  sla_expires_at: string
}

export interface ModuleContribution {
  kind: string
  id: string
}

export interface ModuleInfo {
  name: string
  version: string
  category: string
  state: string
  enabled: boolean
  blocking_reason: string | null
  contributions: ModuleContribution[]
  core: boolean
}

export interface BlockedModule {
  module: string
  check: string
  reason: string
}

export interface ModulesResponse {
  modules: ModuleInfo[]
  blocked: BlockedModule[]
  bundles: unknown[]
  kernel_api: string
  platform_gate_max: string
  readonly: boolean
}

export interface LoginResponse {
  access_token: string
  username?: string
  token_type: string
  role: string
  display_name: string
  shops: ShopRef[]
}

export interface WorkersResponse {
  items: Array<{
    worker_id: string
    kind: string
    status: string
    capabilities: string[]
    queue_depth: number
    last_heartbeat_at: string | null
  }>
  online: number
  empty_copy: string
}

export interface ErrorEnvelope {
  code: string
  layer: 'SYS' | 'DATA' | 'CODE' | 'UI' | string
  message: string
  user_message: string
  retryable: boolean
  details: Record<string, unknown>
}

export interface ModuleActionResponse {
  module: string
  enabled: boolean
  note: string
}

/* ------------------------------------------------------------------ */
/* M1 · P02 评价与口碑                                                 */
/* ------------------------------------------------------------------ */

export interface ReviewTicket {
  ticket_id: string
  run_id: string | null
  platform: string
  shop_id: string
  review_id: string
  sku: string | null
  rating: number | null
  dsr: number | null
  content_masked: string
  hit_rule: string
  severity: 'HIGH' | 'MEDIUM' | string
  status: 'OPEN' | 'ASSIGNED' | 'CLOSED' | string
  assignee: string | null
  sla_due_at: string | null
  created_at: string | null
  closed_at: string | null
  resolution: string | null
  evidence_ref: string | null
  remaining_seconds: number | null
  overdue: boolean
}

export interface ReviewTicketsResponse {
  items: ReviewTicket[]
  counts: Record<string, number>
  empty_copy: string
  readonly: boolean
}

export interface ReviewTrendPoint {
  stat_date: string
  dsr: number | null
  count: number
}

export interface ReviewSummaryResponse {
  platform: string
  shop_id: string
  counts: Record<string, number>
  open: number
  assigned: number
  closed: number
  overdue: number
  trend: ReviewTrendPoint[]
  empty_copy: string
}

export interface ReviewAssignResponse {
  ticket_id: string
  status: string
  assignee: string
}

export interface ReviewCloseResponse {
  ticket_id: string
  status: string
}

/* ------------------------------------------------------------------ */
/* M1 · P03 库存与补货                                                 */
/* ------------------------------------------------------------------ */

export interface InventoryDiff {
  run_id: string
  sku: string
  platform_available: number | null
  erp_available: number | null
  wms_available: number | null
  platform_snapshot_at: string | null
  erp_snapshot_at: string | null
  wms_snapshot_at: string | null
  diff_type: 'STOCKOUT' | 'OVERSELL' | 'MISMATCH' | 'STAGNANT' | 'CONSISTENT' | string
  delta: number | null
  tolerance: number | null
}

export interface InventorySuggestion {
  suggestion_id: string
  run_id: string
  sku: string
  action: 'REPLENISH' | 'PAUSE' | 'SYNC' | string
  quantity: number | null
  reason: string
  status: string
  created_at: string | null
  resolved_at?: string | null
}

export interface InventoryReconciliationResponse {
  run_id: string | null
  window: ReportWindow | null
  diffs: InventoryDiff[]
  suggestions: InventorySuggestion[]
  counts: Record<string, number>
  snapshot_note: string
  empty_copy: string
  readonly: boolean
}

export interface SuggestionActionResponse {
  suggestion_id: string
  status: string
  note: string
}

/* ------------------------------------------------------------------ */
/* P04 活动与投放（S04 投放归集）                                       */
/* ------------------------------------------------------------------ */

export type AdsAlertLevel = 'OK' | 'WATCH' | 'ALERT' | string

export interface AdsCampaign {
  campaign: string
  cost: number
  revenue: number
  roi: number | null
  alert_level: AdsAlertLevel
  suggestion: string
}

export interface AdsTotals {
  cost: number
  revenue: number
  roi: number | null
}

export interface AdsSummaryResponse {
  run_id: string | null
  window: ReportWindow | null
  campaigns: AdsCampaign[]
  counts: Record<string, number>
  totals: AdsTotals
  note: string
  empty_copy: string
  readonly: boolean
}

/* ------------------------------------------------------------------ */
/* M1 · P10 口径与数据合同                                             */
/* ------------------------------------------------------------------ */

export interface ReleaseCheck {
  name: string
  passed: boolean
  detail: string
}

export interface MetricReleaseSummary {
  metric_code: string
  version: string
  gate_passed: boolean
  checks: ReleaseCheck[]
  checked_by?: string | null
  checked_at?: string | null
  note?: string | null
}

export interface MetricCardListItem {
  metric_code: string
  display_name: string
  version: string
  unit: string
  additivity: Additivity | string
  null_policy: string
  source_mapping: string
  release: MetricReleaseSummary | null
}

export interface MetricCardsResponse {
  items: MetricCardListItem[]
  empty_copy: string
}

export interface MetricDiffEntry {
  field: string
  before: unknown
  after: unknown
}

export interface MetricDiffResponse {
  metric_code: string
  from: string | null
  to: string | null
  diffs: MetricDiffEntry[]
  note: string
}

/* ------------------------------------------------------------------ */
/* M1 · P11 机器人与日志                                               */
/* ------------------------------------------------------------------ */

export interface WorkerRegisterResponse {
  worker_id: string
  capabilities: string[]
}

export interface ExceptionRecord {
  id: number
  run_id: string | null
  node_id: string | null
  err_code: string
  err_layer: string
  message: string
  retryable: boolean
  status: string
  screenshot_ref: string | null
  details: Record<string, unknown>
  created_at: string | null
}

export interface ExceptionsResponse {
  items: ExceptionRecord[]
}

/* ------------------------------------------------------------------ */
/* M1 · P12 权限与订阅                                                 */
/* ------------------------------------------------------------------ */

export interface RoleMatrixEntry {
  role: string
  permissions: string[]
}

export interface ShopRoleEntry {
  platform: string
  shop_id: string
  role: string
}

export interface RolesResponse {
  roles: RoleMatrixEntry[]
  shops: ShopRoleEntry[]
  note: string
}

export interface Subscription {
  id: number
  name: string
  event: string
  receiver: string
  channel: string
  window: string
  thresholds: Record<string, number>
  silent_window: string | null
  enabled: boolean
}

export interface SubscriptionsResponse {
  items: Subscription[]
  empty_copy: string
  channels: string[]
}

export interface SubscriptionCreatePayload {
  name: string
  event: string
  receiver: string
  channel: string
  window: string
  thresholds: Record<string, number>
  silent_window: string | null
}

export interface SubscriptionMutationResponse {
  id: number
  status: string
}

export interface NotificationTemplate {
  id: string
  module: string
  event: string
  title: string
  body: string
}

export interface NotificationTemplatesResponse {
  items: NotificationTemplate[]
}

/* ------------------------------------------------------------------ */
/* M2 · P05 新建变更单                                                 */
/* ------------------------------------------------------------------ */

export interface PlatformPriceItem {
  sku: string
  price: string
}

export interface PlatformPriceListResponse {
  items: PlatformPriceItem[]
  campaign_suggestions: string[]
  demo_only: boolean
  note: string
}

export interface CreateWritePlanRow {
  sku: string
  after?: string
  campaign_id?: string
  activity_price?: string
}

export interface CreateWritePlanRequest {
  action_code: string
  platform: string
  shop_id: string
  rows: CreateWritePlanRow[]
  idempotency_key: string
  scene?: string
}

export interface WritePlanCreateResponse {
  plan: WritePlanSummary
  task_id: string
  sla_expires_at: string
}

/* ------------------------------------------------------------------ */
/* M2 · P07 审批记录与审计                                             */
/* ------------------------------------------------------------------ */

export interface ApprovalHistoryItem {
  task_id: string
  change_order_no: string | null
  plan_id: string | null
  action_code: string
  scene: string
  platform: string
  shop_id: string
  status: string
  plan_status: string | null
  execution_status: string | null
  approver: string
  requested_by: string
  rows: number
  sla_expires_at: string | null
  created_at: string | null
}

export interface ApprovalHistoryResponse {
  items: ApprovalHistoryItem[]
  counts: Record<string, number>
  empty_copy: string
}

export interface AuditEntry {
  id?: number
  at: string | null
  actor: string
  action: string
  object_type: string
  object_id: string
  reason: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  ip: string | null
  result: string
}

export interface AuditResponse {
  items: AuditEntry[]
  filters: Record<string, unknown>
}

/* ------------------------------------------------------------------ */
/* P08 对账与差异（S09 结算对账）                                       */
/* ------------------------------------------------------------------ */

export type SettlementDiffType =
  | 'MATCH'
  | 'AMOUNT_DIFF'
  | 'MISSING_SETTLEMENT'
  | 'MISSING_ORDER'
  | string

export interface SettlementDiff {
  order_id: string
  expected_net: number
  settled_amount: number | null
  commission: number | null
  delta: number
  diff_type: SettlementDiffType
  order_ref: string
  settlement_ref: string
  status: string
}

export interface SettlementTotals {
  expected: number
  settled: number
  delta: number
}

export interface SettlementReconciliationResponse {
  run_id: string | null
  window: ReportWindow | null
  diffs: SettlementDiff[]
  counts: Record<string, number>
  totals: SettlementTotals
  note: string
  empty_copy: string
  readonly: boolean
}

/* ------------------------------------------------------------------ */
/* P13 · 1688 选品与采购                                               */
/* ------------------------------------------------------------------ */

/** 后端 Decimal 以字符串序列化；兼容 number 便于测试与前端计算。 */
export type SourcingAmount = number | string

export interface SourcingCandidate {
  run_id?: string
  keyword?: string
  offer_id: string
  title: string
  price: SourcingAmount
  post_fee: SourcingAmount
  moq: number
  sales_30d: number
  supplier: string
  pic_url: string
  url: string
  brand_authorized: boolean
  landed_price?: SourcingAmount
  score: number
  rank: number
  risk_flags: string[]
  risk_label: string
}

export interface SourcingSearchRequest {
  keyword: string
  limit?: number
  filters?: Array<Record<string, unknown>>
}

export interface SourcingSearchResponse {
  run_id: string | null
  status: 'SUCCEEDED' | 'FAILED' | string
  keyword: string
  candidates: SourcingCandidate[]
  count: number
  empty_copy: string
  provider: string
  err_code?: string
  err_layer?: string
}

export interface SourcingCandidatesResponse {
  run_id: string | null
  keyword: string
  candidates: SourcingCandidate[]
  count: number
  empty_copy: string
  provider: string
}

export interface SourcingProviderResponse {
  mode: 'mock' | 'cli' | string
  sourcing_provider: string
  purchase_provider: string
  note: string
}

export type PurchaseStatus =
  | 'AWAITING_CONFIRMATION'
  | 'AWAITING_PAYMENT'
  | 'PAID'
  | 'CANCELLED'
  | 'FAILED'
  | string

export interface PurchaseItem {
  offer_id: string
  title: string
  quantity: number
  unit_price: SourcingAmount
  post_fee: SourcingAmount
  spec_id: string
  subtotal: SourcingAmount
}

export interface PurchaseOrder {
  plan_id: string
  provider: string
  items: PurchaseItem[]
  total: SourcingAmount
  quantity: number
  checkout_id: string
  status: PurchaseStatus
  status_label: string
  continue_url: string
  buyer_note: string
  created_at: string | null
  updated_at: string | null
  task_id: string | null
}

export interface PurchasesResponse {
  items: PurchaseOrder[]
  empty_copy: string
  readonly: boolean
}

export interface PurchaseRefreshResponse extends PurchaseOrder {
  note: string
}

export interface PurchasePlanRow {
  offer_id: string
  quantity: number
}

/** P13 采购单只创建 checkout，支付必须由人在 1688/UTP 完成。 */
export interface CreatePurchasePlanRequest {
  action_code: 'S11.purchase_order' | string
  platform: string
  shop_id: string
  rows: PurchasePlanRow[]
  idempotency_key: string
  scene: string
}

/* ------------------------------------------------------------------ */
/* P14 · 技能中心（S2a：OWNER 可治理）                                  */
/* ------------------------------------------------------------------ */

export type SkillTrust = 'official' | 'verified' | 'community' | 'untrusted' | string

export type SkillRisk = 'L0' | 'L1' | 'L2' | 'L3' | string

/** 目录/详情返回的 Skill 状态；`adapter-only` 表示只有适配器、尚未安装。 */
export type SkillStatus = 'adapter-only' | 'INSTALLED' | 'ENABLED' | 'DISABLED' | string

export interface SkillCapability {
  name: string
  risk: SkillRisk
  risk_label: string
  description: string
}

export interface SkillBinding {
  platform: string
  shop_id: string
  enabled: boolean
  priority: number
  /** 仅存凭据引用（如 vault://...），不含明文凭据。 */
  credential_ref?: string
  config?: Record<string, unknown>
}

/** 安装方式：默认按清单安装，或安装 `storage/skill_packages` 下的 zip 包。 */
export type SkillInstallSource = 'manifest' | 'package'

/** `POST /skills/{id}/install` 请求体；source 为 package 时必须带 package_path。 */
export interface SkillInstallPayload {
  source?: SkillInstallSource
  package_path?: string
}

/** 安装包安装回填的 details：kind=package 时附带包校验和、落盘路径与文件清单。 */
export interface SkillInstallDetails {
  kind?: string
  package_checksum?: string
  package_path?: string
  files?: string[]
  [key: string]: unknown
}

/** `POST /skills/{id}/install|enable|disable` 返回的安装记录。 */
export interface SkillInstallation {
  skill_id: string
  version: string
  status: SkillStatus
  checksum: string
  manifest_path: string
  installed_by: string
  installed_at: string | null
  details?: SkillInstallDetails
  updated_at?: string | null
  /** 仅 install 响应附带：本次安装的边界说明。 */
  note?: string
}

/** `POST /skills/{id}/verify`：expected 为安装时记录的校验和。 */
export interface SkillVerifyResponse {
  skill_id: string
  ok: boolean
  expected: string
  actual: string
}

export interface SkillManifestItem {
  id: string
  version: string
  publisher: string
  trust: SkillTrust
  license: string
  description: string
  adapter: string
  capabilities: SkillCapability[]
  entrypoints: Record<string, unknown>
  limits: Record<string, unknown>
  credentials: string[]
  config: Record<string, unknown>
  checksum: string
  status: SkillStatus
  installed_at?: string | null
  installation?: SkillInstallation | null
  bindings: SkillBinding[]
}

export interface SkillCatalogResponse {
  items: SkillManifestItem[]
  count: number
  lock_path: string
  empty_copy: string
  note: string
}

export interface SkillRun {
  run_id: string
  skill_id: string
  skill_version: string
  capability: string
  scene: string
  platform: string
  shop_id: string
  status: string
  latency_ms: number | null
  error_code: string | null
  created_at: string | null
}

export interface SkillRunsResponse {
  items: SkillRun[]
  empty_copy: string
}

/** `GET /skills/{skill_id}`：清单字段 + 安装记录 + bindings + 最近 20 次运行。 */
export interface SkillDetailResponse extends SkillManifestItem {
  installation?: SkillInstallation | null
  runs: SkillRun[]
}

/** `GET /skills/{skill_id}/bindings`：绑定按 platform + shop_id 匹配。 */
export interface SkillBindingsResponse {
  items: SkillBinding[]
  note: string
}

/** `PUT /skills/{skill_id}/bindings` 请求体。 */
export interface SkillBindingPayload {
  platform: string
  shop_id: string
  enabled: boolean
  priority: number
  credential_ref: string
  config: Record<string, unknown>
}

/** `DELETE /skills/{skill_id}/bindings` 响应。 */
export interface SkillBindingDeleteResponse {
  ok: boolean
}
