<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElButton, ElTable, ElTableColumn } from 'element-plus'

import {
  ApiError,
  assignReviewTicket,
  closeReviewTicket,
  fetchReviewSummary,
  fetchReviewTickets,
} from '../api/client'
import type {
  ReviewSummaryResponse,
  ReviewTicket,
  ReviewTicketsResponse,
} from '../api/types'
import { zhCN, type Tone } from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useContextStore } from '../stores/context'
import { useToast } from '../composables/useToast'
import { formatSlaCountdown } from '../utils/format'
import ActionDialog from '../components/ActionDialog.vue'
import KpiTile from '../components/KpiTile.vue'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'
import TrendBars from '../components/TrendBars.vue'

type DialogMode = 'assign' | 'close'

const session = useSessionStore()
const context = useContextStore()
const { push } = useToast()

const ticketsPayload = ref<ReviewTicketsResponse | null>(null)
const summary = ref<ReviewSummaryResponse | null>(null)
const loading = ref(true)
const summaryLoading = ref(true)
const errorText = ref('')
const summaryError = ref('')

const dialogOpen = ref(false)
const dialogMode = ref<DialogMode>('assign')
const dialogTarget = ref<ReviewTicket | null>(null)
const dialogError = ref('')
const actionPending = ref(false)

const nowTick = ref(Date.now())
let loadedAt = Date.now()
let clockTimer: number | null = null
let requestSeq = 0
let summarySeq = 0

const role = computed(() => session.role || context.role)
const canHandle = computed(() => role.value === 'OWNER' || role.value === 'EDITOR')
const isViewer = computed(() => role.value === 'VIEWER')
const tickets = computed(() => ticketsPayload.value?.items ?? [])
const emptyCopy = computed(() => ticketsPayload.value?.empty_copy || zhCN.p02.empty)
const trend = computed(() => summary.value?.trend ?? [])

const elapsedSeconds = computed(() => Math.max(0, Math.floor((nowTick.value - loadedAt) / 1000)))
const hasKpiData = computed(() => Boolean(ticketsPayload.value || summary.value))

const kpis = computed<Array<{ label: string; value: number | string; code: string; tone: Tone }>>(
  () => {
    const fallbackCounts = ticketsPayload.value?.counts ?? {}
    const overdueFallback = tickets.value.filter((ticket) => ticket.overdue).length
    const emptyValue = zhCN.common.none
    return [
      {
        label: zhCN.p02.kpi.open,
        value: hasKpiData.value ? (summary.value?.open ?? fallbackCounts.OPEN ?? 0) : emptyValue,
        code: 'OPEN',
        tone: 'warning',
      },
      {
        label: zhCN.p02.kpi.assigned,
        value: hasKpiData.value
          ? (summary.value?.assigned ?? fallbackCounts.ASSIGNED ?? 0)
          : emptyValue,
        code: 'ASSIGNED',
        tone: 'info',
      },
      {
        label: zhCN.p02.kpi.overdue,
        value: hasKpiData.value ? (summary.value?.overdue ?? overdueFallback) : emptyValue,
        code: 'OVERDUE',
        tone: 'danger',
      },
      {
        label: zhCN.p02.kpi.closed,
        value: hasKpiData.value
          ? (summary.value?.closed ?? fallbackCounts.CLOSED ?? 0)
          : emptyValue,
        code: 'CLOSED',
        tone: 'success',
      },
    ]
  },
)

const dialogConfig = computed(() => {
  if (dialogMode.value === 'assign') {
    return {
      title: zhCN.p02.actions.assignTitle,
      description: zhCN.p02.actions.assignDescription,
      fieldLabel: zhCN.p02.actions.assignee,
      placeholder: zhCN.p02.actions.assigneePlaceholder,
      confirmLabel: zhCN.p02.actions.assignConfirm,
      required: true,
      multiline: false,
    }
  }
  return {
    title: zhCN.p02.actions.closeTitle,
    description: zhCN.p02.actions.closeDescription,
    fieldLabel: zhCN.p02.actions.resolution,
    placeholder: zhCN.p02.actions.resolutionPlaceholder,
    confirmLabel: zhCN.p02.actions.closeConfirm,
    required: true,
    multiline: true,
  }
})

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError) return cause.userMessage || fallback
  if (cause && typeof cause === 'object' && 'userMessage' in cause) {
    return String((cause as { userMessage: unknown }).userMessage) || fallback
  }
  return fallback
}

function severityLabel(severity: string): string {
  return zhCN.p02.severity[severity] ?? severity
}

function severityTone(severity: string): Tone {
  if (severity === 'HIGH') return 'danger'
  if (severity === 'MEDIUM') return 'warning'
  return 'neutral'
}

function remainingFor(ticket: ReviewTicket): number | null {
  if (ticket.remaining_seconds === null || ticket.remaining_seconds === undefined) return null
  return ticket.remaining_seconds - elapsedSeconds.value
}

function slaView(row: unknown): { text: string; overdue: boolean } {
  const ticket = row as ReviewTicket
  if (ticket.status === 'CLOSED') return { text: zhCN.common.none, overdue: false }
  const remaining = remainingFor(ticket)
  if (remaining === null) return { text: zhCN.common.none, overdue: false }
  if (ticket.overdue || remaining <= 0) return { text: zhCN.p02.sla.overdue, overdue: true }
  return { text: formatSlaCountdown(remaining), overdue: false }
}

async function loadTickets(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  errorText.value = ''
  try {
    const payload = await fetchReviewTickets()
    if (seq !== requestSeq) return
    ticketsPayload.value = payload
    loadedAt = Date.now()
    nowTick.value = loadedAt
  } catch (cause) {
    if (seq !== requestSeq) return
    errorText.value = errorMessage(cause, zhCN.p02.loadFailed)
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

async function loadSummary(): Promise<void> {
  const seq = ++summarySeq
  summaryLoading.value = true
  summaryError.value = ''
  try {
    const payload = await fetchReviewSummary()
    if (seq !== summarySeq) return
    summary.value = payload
  } catch (cause) {
    if (seq !== summarySeq) return
    summaryError.value = errorMessage(cause, zhCN.p02.summaryLoadFailed)
  } finally {
    if (seq === summarySeq) summaryLoading.value = false
  }
}

async function refreshAll(): Promise<void> {
  await Promise.allSettled([loadTickets(), loadSummary()])
}

function openAction(row: unknown, mode: DialogMode): void {
  dialogTarget.value = row as ReviewTicket
  dialogMode.value = mode
  dialogError.value = ''
  dialogOpen.value = true
}

function closeAction(): void {
  if (actionPending.value) return
  dialogOpen.value = false
  dialogTarget.value = null
  dialogError.value = ''
}

async function submitAction(value: string): Promise<void> {
  const ticket = dialogTarget.value
  if (!ticket) return
  actionPending.value = true
  dialogError.value = ''
  try {
    if (dialogMode.value === 'assign') {
      await assignReviewTicket(ticket.ticket_id, value)
    } else {
      await closeReviewTicket(ticket.ticket_id, value)
    }
    push(zhCN.p02.actionSuccess, 'success')
    dialogOpen.value = false
    dialogTarget.value = null
    await refreshAll()
  } catch (cause) {
    dialogError.value = errorMessage(cause, zhCN.p02.actionFailed)
    push(dialogError.value, 'danger')
  } finally {
    actionPending.value = false
  }
}

function startClock(): void {
  if (typeof window === 'undefined') return
  clockTimer = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
}

onMounted(() => {
  void refreshAll()
  startClock()
})

onBeforeUnmount(() => {
  if (clockTimer !== null) {
    window.clearInterval(clockTimer)
    clockTimer = null
  }
})
</script>

<template>
  <div class="sp-page sp-p02">
    <PageHeader
      :eyebrow="zhCN.p02.eyebrow"
      :title="zhCN.p02.title"
      :description="zhCN.p02.description"
    >
      <template #meta>
        <StatusBadge v-if="isViewer" :label="zhCN.p02.readonlyHint" tone="neutral" />
      </template>
      <template #actions>
        <ElButton size="small" :loading="loading" @click="refreshAll">{{ zhCN.p02.refresh }}</ElButton>
      </template>
    </PageHeader>

    <div class="sp-p02__masked" role="note">{{ zhCN.p02.masked }}</div>

    <section class="sp-p02__kpis" :aria-label="zhCN.p02.title">
      <KpiTile
        v-for="item in kpis"
        :key="item.code"
        :label="item.label"
        :value="item.value"
        :code="item.code"
        :tone="item.tone"
      />
    </section>

    <section class="sp-panel sp-p02__trend">
      <div class="sp-panel__header">
        <div class="sp-panel__title">{{ zhCN.p02.trend.title }}</div>
        <span class="sp-panel__hint">{{ zhCN.p02.trend.hint }}</span>
      </div>
      <div class="sp-p02__trend-body">
        <StateView v-if="summaryLoading" state="loading" compact />
        <StateView
          v-else-if="summaryError"
          state="error"
          :title="zhCN.p02.summaryLoadFailed"
          :description="summaryError"
          compact
          @retry="loadSummary"
        />
        <StateView
          v-else-if="!trend.length"
          state="empty"
          :title="zhCN.p02.trend.empty"
          compact
        />
        <TrendBars v-else :points="trend" />
      </div>
    </section>

    <section class="sp-panel sp-p02__table-panel">
      <div class="sp-panel__header">
        <div class="sp-panel__title">
          <span>{{ zhCN.p02.tableTitle }}</span>
          <span v-if="tickets.length" class="sp-panel__count">{{ tickets.length }}</span>
        </div>
        <div class="sp-p02__table-hint">
          <span>{{ zhCN.p02.tableHint }}</span>
          <StatusBadge v-if="isViewer" :label="zhCN.p02.readonlyHint" tone="neutral" />
        </div>
      </div>

      <StateView v-if="loading" state="loading" compact />
      <StateView
        v-else-if="errorText"
        state="error"
        :title="zhCN.p02.loadFailed"
        :description="errorText"
        compact
        @retry="loadTickets"
      />
      <StateView
        v-else-if="!tickets.length"
        state="empty"
        :title="emptyCopy"
        :description="zhCN.p02.emptyHint"
        compact
      />
      <ElTable v-else :data="tickets" size="small" border style="width: 100%">
        <ElTableColumn :label="zhCN.p02.columns.severity" width="76">
          <template #default="{ row }">
            <StatusBadge :label="severityLabel(row.severity)" :tone="severityTone(row.severity)" />
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p02.columns.sku" min-width="150">
          <template #default="{ row }">
            <div class="sp-p02__sku">{{ row.sku || zhCN.common.none }}</div>
            <div class="sp-p02__review sp-mono">{{ row.review_id }}</div>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p02.columns.rating" width="76">
          <template #default="{ row }">
            <span class="sp-mono">
              {{ row.rating ?? zhCN.common.none
              }}<span v-if="typeof row.rating === 'number'" class="sp-p02__unit">{{ zhCN.p02.ratingUnit }}</span>
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p02.columns.content" min-width="220">
          <template #default="{ row }">
            <span class="sp-p02__content" :title="row.content_masked">
              {{ row.content_masked || zhCN.common.none }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p02.columns.rule" min-width="120">
          <template #default="{ row }">
            <span class="sp-chip">{{ row.hit_rule || zhCN.common.none }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p02.columns.status" width="88">
          <template #default="{ row }">
            <StatusBadge :status="row.status" />
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p02.columns.sla" width="106">
          <template #default="{ row }">
            <span
              class="sp-p02__sla sp-mono"
              :class="{ 'is-overdue': slaView(row).overdue }"
            >
              {{ slaView(row).text }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p02.columns.assignee" width="96">
          <template #default="{ row }">
            {{ row.assignee || zhCN.common.none }}
          </template>
        </ElTableColumn>
        <ElTableColumn v-if="canHandle" :label="zhCN.p02.columns.actions" width="128" fixed="right">
          <template #default="{ row }">
            <div v-if="row.status === 'OPEN' || row.status === 'ASSIGNED'" class="sp-p02__actions">
              <ElButton size="small" @click="openAction(row, 'assign')">
                {{ zhCN.p02.actions.assign }}
              </ElButton>
              <ElButton size="small" @click="openAction(row, 'close')">
                {{ zhCN.p02.actions.close }}
              </ElButton>
            </div>
            <span v-else class="sp-faint">{{ zhCN.common.none }}</span>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>

    <ActionDialog
      :open="dialogOpen"
      v-bind="dialogConfig"
      :pending="actionPending"
      :error="dialogError"
      @confirm="submitAction"
      @cancel="closeAction"
    />
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p02__masked {
  padding: 6px 11px;
  border: 1px solid var(--sp-info-border);
  border-left: 3px solid var(--sp-info);
  border-radius: var(--sp-radius);
  background: var(--sp-info-soft);
  color: var(--sp-info);
  font-size: 11.5px;
}

.sp-p02__kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.sp-p02__trend-body {
  padding: 10px 12px;
}

.sp-p02__table-panel {
  overflow: hidden;
}

.sp-p02__table-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-p02__sku {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--sp-text);
}

.sp-p02__review {
  font-size: 10px;
  color: var(--sp-faint);
}

.sp-p02__unit {
  margin-left: 2px;
  font-size: 10px;
  color: var(--sp-faint);
}

.sp-p02__content {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--sp-muted);
}

.sp-p02__sla {
  font-variant-numeric: tabular-nums;
  color: var(--sp-text);
}

.sp-p02__sla.is-overdue {
  color: var(--sp-warning);
  font-weight: 600;
}

.sp-p02__actions {
  display: flex;
  gap: 6px;
}

@media (max-width: 1080px) {
  .sp-p02__kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .sp-p02__kpis {
    grid-template-columns: minmax(0, 1fr);
  }
  .sp-p02__table-hint {
    display: none;
  }
}
</style>
