<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ElButton, ElTable, ElTableColumn } from 'element-plus'

import { ApiError, fetchApprovalHistory, fetchAudit, fetchChangeOrder } from '../api/client'
import type {
  ApprovalHistoryItem,
  ApprovalHistoryResponse,
  AuditEntry,
  ChangeOrderPayload,
} from '../api/types'
import { EMPTY_APPROVALS_COPY, zhCN } from '../i18n/zh-CN'
import { formatDateTime, truncateHead } from '../utils/format'
import { labelForStatus } from '../utils/status'
import BeforeAfterTable from '../components/BeforeAfterTable.vue'
import DrawerPanel from '../components/DrawerPanel.vue'
import EvidencePack from '../components/EvidencePack.vue'
import ExecutionPanel from '../components/ExecutionPanel.vue'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

interface AppliedFilters {
  status: string
  actionCode: string
  approver: string
}

const payload = ref<ApprovalHistoryResponse | null>(null)
const loading = ref(true)
const errorText = ref('')
const forbidden = ref(false)

const statusFilter = ref('')
const actionFilter = ref('')
const approverFilter = ref('')
const appliedFilters = ref<AppliedFilters>({ status: '', actionCode: '', approver: '' })

const drawerOpen = ref(false)
const target = ref<ApprovalHistoryItem | null>(null)
const auditItems = ref<AuditEntry[]>([])
const auditLoading = ref(false)
const auditError = ref('')
const detail = ref<ChangeOrderPayload | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

let requestSeq = 0
let drawerSeq = 0

const rows = computed(() => payload.value?.items ?? [])
const emptyCopy = computed(() => payload.value?.empty_copy || EMPTY_APPROVALS_COPY)
const totalCount = computed(() => rows.value.length)
const statusOptions = computed(() => zhCN.p07.statusOptions)
const actionOptions = computed(() => zhCN.p07.actionOptions)

const summaryFields = computed<Array<{ label: string; value: string; mono?: boolean }>>(() => {
  const item = target.value
  if (!item) return []
  const fields = zhCN.p07.drawer.fields
  return [
    { label: fields.changeOrderNo, value: changeOrderLabel(item), mono: true },
    { label: fields.taskId, value: item.task_id, mono: true },
    { label: fields.planId, value: item.plan_id || zhCN.common.none, mono: true },
    { label: fields.action, value: item.action_code, mono: true },
    { label: fields.scene, value: item.scene || zhCN.common.none, mono: true },
    {
      label: fields.platform,
      value: `${item.platform} / ${item.shop_id}`,
      mono: true,
    },
    { label: fields.status, value: labelForStatus(item.status) },
    { label: fields.planStatus, value: item.plan_status ? labelForStatus(item.plan_status) : zhCN.common.none },
    {
      label: fields.executionStatus,
      value: item.execution_status ? labelForStatus(item.execution_status) : zhCN.common.none,
    },
    { label: fields.approver, value: item.approver || zhCN.common.none },
    { label: fields.requestedBy, value: item.requested_by || zhCN.common.none },
    { label: fields.rows, value: String(item.rows) },
    { label: fields.sla, value: formatDateTime(item.sla_expires_at) || zhCN.common.none },
    { label: fields.createdAt, value: formatDateTime(item.created_at) || zhCN.common.none },
  ]
})

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError) return cause.message || cause.userMessage || fallback
  if (cause && typeof cause === 'object') {
    if ('userMessage' in cause) {
      const message = String((cause as { userMessage: unknown }).userMessage)
      if (message) return message
    }
    if ('message' in cause && typeof cause.message === 'string' && cause.message) {
      return cause.message
    }
  }
  return fallback
}

function actionLabel(code: string): string {
  return zhCN.p07.actionLabels[code] ?? code
}

function changeOrderLabel(row: unknown): string {
  const item = row as ApprovalHistoryItem
  if (item.change_order_no) return item.change_order_no
  return truncateHead(item.task_id, 10)
}

function atValue(value: string | null): number {
  const parsed = value ? Date.parse(value) : Number.NaN
  return Number.isNaN(parsed) ? 0 : parsed
}

async function load(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  errorText.value = ''
  forbidden.value = false
  try {
    const response = await fetchApprovalHistory({
      limit: 100,
      status: appliedFilters.value.status,
      actionCode: appliedFilters.value.actionCode,
      approver: appliedFilters.value.approver,
    })
    if (seq !== requestSeq) return
    payload.value = response
  } catch (cause) {
    if (seq !== requestSeq) return
    if (cause instanceof ApiError && cause.status === 403) {
      payload.value = null
      forbidden.value = true
      return
    }
    errorText.value = errorMessage(cause, zhCN.p07.loadFailed)
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function query(): void {
  appliedFilters.value = {
    status: statusFilter.value,
    actionCode: actionFilter.value,
    approver: approverFilter.value.trim(),
  }
  void load()
}

function resetFilters(): void {
  statusFilter.value = ''
  actionFilter.value = ''
  approverFilter.value = ''
  appliedFilters.value = { status: '', actionCode: '', approver: '' }
  void load()
}

async function loadAudit(objectId: string, seq: number): Promise<void> {
  try {
    const response = await fetchAudit({ objectId, limit: 100 })
    if (seq !== drawerSeq) return
    auditItems.value = [...(response.items ?? [])].sort((left, right) => atValue(right.at) - atValue(left.at))
  } catch (cause) {
    if (seq !== drawerSeq) return
    auditError.value = errorMessage(cause, zhCN.p07.drawer.auditFailed)
  } finally {
    if (seq === drawerSeq) auditLoading.value = false
  }
}

async function loadDetail(taskId: string, seq: number): Promise<void> {
  try {
    const response = await fetchChangeOrder(taskId)
    if (seq !== drawerSeq) return
    detail.value = response
  } catch (cause) {
    if (seq !== drawerSeq) return
    detailError.value = errorMessage(cause, zhCN.p07.drawer.detailFailed)
  } finally {
    if (seq === drawerSeq) detailLoading.value = false
  }
}

function openItem(item: ApprovalHistoryItem): void {
  const seq = ++drawerSeq
  target.value = item
  drawerOpen.value = true
  auditItems.value = []
  auditError.value = ''
  auditLoading.value = true
  detail.value = null
  detailError.value = ''
  detailLoading.value = Boolean(item.plan_id)
  const objectId = item.plan_id || item.task_id
  void loadAudit(objectId, seq)
  if (item.plan_id) void loadDetail(item.task_id, seq)
}

function openRecord(row: unknown): void {
  openItem(row as ApprovalHistoryItem)
}

function closeDrawer(): void {
  drawerSeq += 1
  drawerOpen.value = false
  target.value = null
  auditItems.value = []
  auditError.value = ''
  auditLoading.value = false
  detail.value = null
  detailError.value = ''
  detailLoading.value = false
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="sp-page sp-p07">
    <PageHeader
      :eyebrow="zhCN.p07.eyebrow"
      :title="zhCN.p07.title"
      :description="zhCN.p07.description"
    >
      <template #meta>
        <span>{{ zhCN.p07.total.replace('{count}', String(totalCount)) }}</span>
        <StatusBadge v-if="forbidden" :label="zhCN.p07.forbidden" tone="neutral" />
      </template>
      <template #actions>
        <ElButton size="small" :loading="loading" @click="load">{{ zhCN.p07.refresh }}</ElButton>
      </template>
    </PageHeader>

    <section class="sp-panel sp-p07__filters">
      <div class="sp-panel__header">
        <div class="sp-panel__title">{{ zhCN.p07.filters.title }}</div>
      </div>
      <div class="sp-p07__filter-body">
        <label class="sp-p07__filter">
          <span class="sp-p07__filter-label">{{ zhCN.p07.filters.status }}</span>
          <select v-model="statusFilter" class="sp-p07__control" data-filter="status">
            <option value="">{{ zhCN.p07.filters.all }}</option>
            <option v-for="status in statusOptions" :key="status" :value="status">
              {{ labelForStatus(status) }}
            </option>
          </select>
        </label>
        <label class="sp-p07__filter">
          <span class="sp-p07__filter-label">{{ zhCN.p07.filters.action }}</span>
          <select v-model="actionFilter" class="sp-p07__control" data-filter="action_code">
            <option value="">{{ zhCN.p07.filters.all }}</option>
            <option v-for="code in actionOptions" :key="code" :value="code">
              {{ actionLabel(code) }}
            </option>
          </select>
        </label>
        <label class="sp-p07__filter sp-p07__filter--grow">
          <span class="sp-p07__filter-label">{{ zhCN.p07.filters.approver }}</span>
          <input
            v-model="approverFilter"
            class="sp-p07__control"
            type="text"
            data-filter="approver"
            :placeholder="zhCN.p07.filters.approverPlaceholder"
            @keyup.enter="query"
          />
        </label>
        <div class="sp-p07__filter-actions">
          <ElButton
            size="small"
            type="primary"
            data-action="query"
            :loading="loading"
            @click="query"
          >
            {{ zhCN.p07.filters.query }}
          </ElButton>
          <ElButton size="small" :disabled="loading" @click="resetFilters">
            {{ zhCN.p07.filters.reset }}
          </ElButton>
        </div>
      </div>
    </section>

    <section class="sp-panel sp-p07__table-panel">
      <div class="sp-panel__header">
        <div class="sp-panel__title">
          <span>{{ zhCN.p07.title }}</span>
          <span v-if="rows.length" class="sp-panel__count">{{ rows.length }}</span>
        </div>
        <span class="sp-panel__hint">{{ zhCN.p07.tableHint }}</span>
      </div>

      <StateView v-if="loading" state="loading" compact />
      <StateView
        v-else-if="forbidden"
        state="forbidden"
        :title="zhCN.p07.forbidden"
        :description="zhCN.p07.forbiddenHint"
        :retryable="false"
        compact
      />
      <StateView
        v-else-if="errorText"
        state="error"
        :title="zhCN.p07.loadFailed"
        :description="errorText"
        compact
        @retry="load"
      />
      <StateView
        v-else-if="!rows.length"
        state="empty"
        :title="emptyCopy"
        :description="zhCN.p07.emptyHint"
        compact
      />
      <ElTable
        v-else
        :data="rows"
        size="small"
        border
        row-key="task_id"
        style="width: 100%"
        @row-click="openRecord"
      >
        <ElTableColumn :label="zhCN.p07.columns.createdAt" width="150">
          <template #default="{ row }">
            <span class="sp-mono sp-p07__time">
              {{ formatDateTime(row.created_at) || zhCN.common.none }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p07.columns.changeOrderNo" min-width="172">
          <template #default="{ row }">
            <button
              type="button"
              class="sp-link-btn sp-mono"
              data-open="record"
              :aria-label="zhCN.p07.openRow"
              @click.stop="openRecord(row)"
            >
              {{ changeOrderLabel(row) }}
            </button>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p07.columns.action" min-width="176">
          <template #default="{ row }">
            <div class="sp-p07__action">
              <span>{{ actionLabel(row.action_code) }}</span>
              <span class="sp-mono sp-faint">{{ row.action_code }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p07.columns.approver" width="104">
          <template #default="{ row }">{{ row.approver || zhCN.common.none }}</template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p07.columns.status" width="104">
          <template #default="{ row }">
            <StatusBadge :status="row.status" />
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p07.columns.execution" width="112">
          <template #default="{ row }">
            <StatusBadge v-if="row.execution_status" :status="row.execution_status" />
            <span v-else class="sp-faint">{{ zhCN.common.none }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p07.columns.rows" width="72" align="right">
          <template #default="{ row }">
            <span class="sp-mono">{{ row.rows }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p07.columns.sla" width="150">
          <template #default="{ row }">
            <span class="sp-mono sp-p07__time">
              {{ formatDateTime(row.sla_expires_at) || zhCN.common.none }}
            </span>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>

    <DrawerPanel
      :open="drawerOpen"
      :title="zhCN.p07.drawer.title"
      :subtitle="target ? changeOrderLabel(target) : zhCN.p07.drawer.subtitle"
      width="680px"
      :close-label="zhCN.p07.drawer.close"
      @close="closeDrawer"
    >
      <div v-if="target" class="sp-p07__detail">
        <div class="sp-p07__detail-head">
          <span class="sp-mono sp-p07__detail-no">{{ changeOrderLabel(target) }}</span>
          <StatusBadge :status="target.status" dot />
          <StatusBadge v-if="target.execution_status" :status="target.execution_status" />
        </div>

        <section class="sp-p07__sub">
          <h3>{{ zhCN.p07.drawer.summary }}</h3>
          <dl class="sp-p07__kv">
            <template v-for="field in summaryFields" :key="field.label">
              <dt>{{ field.label }}</dt>
              <dd :class="{ 'sp-mono': field.mono }">{{ field.value }}</dd>
            </template>
          </dl>
        </section>

        <section class="sp-p07__sub">
          <h3>{{ zhCN.p07.drawer.audit }}</h3>
          <StateView v-if="auditLoading" state="loading" compact />
          <StateView
            v-else-if="auditError"
            state="error"
            :title="zhCN.p07.drawer.auditFailed"
            :description="auditError"
            compact
          />
          <p v-else-if="!auditItems.length" class="sp-p07__empty-line">
            {{ zhCN.p07.drawer.auditEmpty }}
          </p>
          <ol v-else class="sp-p07__timeline">
            <li
              v-for="(entry, index) in auditItems"
              :key="entry.id ?? `${entry.at}-${index}`"
              class="sp-p07__timeline-item"
            >
              <div class="sp-p07__timeline-head">
                <span class="sp-mono sp-p07__time">
                  {{ formatDateTime(entry.at) || zhCN.common.none }}
                </span>
                <span class="sp-chip">{{ entry.result || 'OK' }}</span>
              </div>
              <div class="sp-p07__timeline-main">
                <span class="sp-mono sp-p07__timeline-action">{{ entry.action }}</span>
                <span class="sp-p07__timeline-actor">
                  {{ zhCN.p07.drawer.auditFields.actor }} · {{ entry.actor }}
                </span>
              </div>
              <p v-if="entry.reason" class="sp-p07__timeline-reason">
                {{ zhCN.p07.drawer.auditFields.reason }} · {{ entry.reason }}
              </p>
            </li>
          </ol>
        </section>

        <section class="sp-p07__sub">
          <h3>{{ zhCN.p07.drawer.evidence }}</h3>
          <template v-if="target.plan_id">
            <StateView v-if="detailLoading" state="loading" compact />
            <StateView
              v-else-if="detailError"
              state="error"
              :title="zhCN.p07.drawer.detailFailed"
              :description="detailError"
              compact
            />
            <template v-else-if="detail">
              <dl class="sp-p07__kv">
                <dt>{{ zhCN.p06.sections.impact }}</dt>
                <dd>{{ detail.impact_scope || zhCN.p06.rollback.impactEmpty }}</dd>
              </dl>
              <BeforeAfterTable :rows="detail.before_after" />
              <EvidencePack :items="detail.evidence" :complete="detail.evidence_complete" />
              <ExecutionPanel
                v-if="detail.execution"
                :execution="detail.execution"
                :plan-status="detail.plan_status"
              />
              <p v-else class="sp-p07__empty-line">{{ zhCN.p07.drawer.noExecution }}</p>
            </template>
          </template>
          <p v-else class="sp-p07__empty-line">{{ zhCN.p07.drawer.noPlan }}</p>
        </section>

        <RouterLink
          v-if="target.task_id"
          class="sp-p07__p06-link"
          :to="`/change-orders/${encodeURIComponent(target.task_id)}`"
        >
          {{ zhCN.p07.drawer.openP06 }}
        </RouterLink>
      </div>
    </DrawerPanel>
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p07__filters {
  overflow: hidden;
}

.sp-p07__filter-body {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 14px 12px;
  background: var(--sp-bg);
}

.sp-p07__filter {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 128px;
}

.sp-p07__filter--grow {
  flex: 1;
  min-width: 180px;
}

.sp-p07__filter-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-p07__control {
  width: 100%;
  height: 30px;
  padding: 0 9px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  font-size: 12.5px;
  color: var(--sp-text);
}

.sp-p07__control:focus {
  border-color: var(--sp-primary);
  outline: none;
}

.sp-p07__filter-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sp-p07__table-panel {
  overflow: hidden;
}

.sp-p07__table-panel :deep(.el-table__row) {
  cursor: pointer;
}

.sp-p07__time {
  font-size: 11.5px;
  color: var(--sp-muted);
  white-space: nowrap;
}

.sp-p07__action {
  display: flex;
  flex-direction: column;
  gap: 1px;
  line-height: 1.35;
}

.sp-p07__detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p07__detail-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.sp-p07__detail-no {
  font-size: 13px;
  font-weight: 600;
}

.sp-p07__sub {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sp-p07__sub h3 {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--sp-muted);
}

.sp-p07__kv {
  display: grid;
  grid-template-columns: 108px minmax(0, 1fr);
  gap: 4px 10px;
  padding: 9px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 12px;
}

.sp-p07__kv dt {
  color: var(--sp-muted);
}

.sp-p07__kv dd {
  min-width: 0;
  word-break: break-word;
}

.sp-p07__timeline {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  overflow: hidden;
}

.sp-p07__timeline-item {
  padding: 8px 10px;
  border-bottom: 1px solid var(--sp-border);
  background: var(--sp-surface);
}

.sp-p07__timeline-item:last-child {
  border-bottom: 0;
}

.sp-p07__timeline-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sp-p07__timeline-main {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 2px;
}

.sp-p07__timeline-action {
  font-size: 12px;
  color: var(--sp-text);
}

.sp-p07__timeline-actor {
  font-size: 11px;
  color: var(--sp-muted);
}

.sp-p07__timeline-reason {
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--sp-muted);
}

.sp-p07__empty-line {
  padding: 12px;
  border: 1px dashed var(--sp-border);
  border-radius: var(--sp-radius-sm);
  font-size: 12px;
  color: var(--sp-muted);
  text-align: center;
}

.sp-p07__p06-link {
  align-self: flex-start;
  font-size: 12px;
  font-weight: 500;
}
</style>
