<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElButton, ElTable, ElTableColumn } from 'element-plus'

import {
  ApiError,
  acceptInventorySuggestion,
  fetchInventoryReconciliation,
  ignoreInventorySuggestion,
} from '../api/client'
import type {
  InventoryDiff,
  InventoryReconciliationResponse,
  InventorySuggestion,
} from '../api/types'
import { zhCN, type Tone } from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useContextStore } from '../stores/context'
import { useToast } from '../composables/useToast'
import { formatDate, formatDateTime } from '../utils/format'
import ActionDialog from '../components/ActionDialog.vue'
import KpiTile from '../components/KpiTile.vue'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

type DialogMode = 'accept' | 'ignore'

const session = useSessionStore()
const context = useContextStore()
const { push } = useToast()

const payload = ref<InventoryReconciliationResponse | null>(null)
const loading = ref(true)
const errorText = ref('')
const dialogOpen = ref(false)
const dialogMode = ref<DialogMode>('accept')
const dialogTarget = ref<InventorySuggestion | null>(null)
const dialogError = ref('')
const actionPending = ref(false)
let requestSeq = 0

const role = computed(() => session.role || context.role)
const canHandle = computed(() => role.value === 'OWNER' || role.value === 'EDITOR')
const isViewer = computed(() => role.value === 'VIEWER')
const diffs = computed<InventoryDiff[]>(() => payload.value?.diffs ?? [])
const suggestions = computed<InventorySuggestion[]>(() => payload.value?.suggestions ?? [])
const emptyCopy = computed(() => payload.value?.empty_copy || zhCN.p03.empty)
const snapshotNote = computed(
  () => payload.value?.snapshot_note || zhCN.p03.snapshotNoteFallback,
)

const windowText = computed(() => {
  const window = payload.value?.window
  if (!window) return ''
  return `${formatDate(window.start)} ~ ${formatDate(window.end)}`
})

const kpiCodes = ['STOCKOUT', 'OVERSELL', 'MISMATCH', 'STAGNANT', 'CONSISTENT'] as const
const kpiTones: Record<(typeof kpiCodes)[number], Tone> = {
  STOCKOUT: 'danger',
  OVERSELL: 'warning',
  MISMATCH: 'info',
  STAGNANT: 'neutral',
  CONSISTENT: 'success',
}
const kpis = computed(() =>
  kpiCodes.map((code) => ({
    code,
    label: zhCN.p03.kpi[code] ?? code,
    value: payload.value ? Number(payload.value.counts?.[code] ?? 0) : zhCN.common.none,
    tone: kpiTones[code],
  })),
)

const dialogConfig = computed(() => {
  if (dialogMode.value === 'accept') {
    return {
      title: zhCN.p03.acceptTitle,
      fieldLabel: zhCN.p03.note,
      placeholder: zhCN.p03.notePlaceholder,
      confirmLabel: zhCN.p03.acceptConfirm,
      required: false,
      multiline: true,
    }
  }
  return {
    title: zhCN.p03.ignoreTitle,
    fieldLabel: zhCN.p03.note,
    placeholder: zhCN.p03.notePlaceholder,
    confirmLabel: zhCN.p03.ignoreConfirm,
    required: false,
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

function diffLabel(type: string): string {
  return zhCN.p03.diffLabels[type] ?? type
}

function actionLabel(action: string): string {
  return zhCN.p03.actionLabels[action] ?? action
}

function suggestionStatusLabel(status: string): string {
  return zhCN.p03.suggestionStatus[status] ?? status
}

function suggestionTone(status: string): Tone {
  if (status === 'ACCEPTED') return 'success'
  if (status === 'IGNORED') return 'neutral'
  return 'warning'
}

function availableText(value: number | null): string {
  return value === null || value === undefined ? zhCN.common.none : String(value)
}

function numberText(value: number | null): string {
  return value === null || value === undefined ? zhCN.common.none : String(value)
}

function timeText(value: string | null): string {
  return formatDateTime(value) || zhCN.common.none
}

async function load(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  errorText.value = ''
  try {
    const response = await fetchInventoryReconciliation()
    if (seq !== requestSeq) return
    payload.value = response
  } catch (cause) {
    if (seq !== requestSeq) return
    errorText.value = errorMessage(cause, zhCN.p03.loadFailed)
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function openAction(row: unknown, mode: DialogMode): void {
  dialogTarget.value = row as InventorySuggestion
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

async function submitAction(note: string): Promise<void> {
  const suggestion = dialogTarget.value
  if (!suggestion) return
  actionPending.value = true
  dialogError.value = ''
  try {
    if (dialogMode.value === 'accept') {
      await acceptInventorySuggestion(suggestion.suggestion_id, note)
    } else {
      await ignoreInventorySuggestion(suggestion.suggestion_id, note)
    }
    push(zhCN.p03.actionSuccess, 'success')
    dialogOpen.value = false
    dialogTarget.value = null
    await load()
  } catch (cause) {
    dialogError.value = errorMessage(cause, zhCN.p03.actionFailed)
    push(dialogError.value, 'danger')
  } finally {
    actionPending.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="sp-page sp-p03">
    <PageHeader
      :eyebrow="zhCN.p03.eyebrow"
      :title="zhCN.p03.title"
      :description="zhCN.p03.description"
    >
      <template #meta>
        <span v-if="payload?.run_id">
          <span class="sp-faint">{{ zhCN.status.runId }}</span>
          <span class="sp-p03__meta sp-mono">{{ payload.run_id }}</span>
        </span>
        <span v-if="windowText">
          <span class="sp-faint">{{ zhCN.context.window }}</span>
          <span class="sp-p03__meta">{{ windowText }}</span>
        </span>
        <StatusBadge v-if="isViewer" :label="zhCN.p03.readonlyHint" tone="neutral" />
      </template>
      <template #actions>
        <ElButton size="small" :loading="loading" @click="load">{{ zhCN.p03.refresh }}</ElButton>
      </template>
    </PageHeader>

    <div class="sp-p03__snapshot" role="note">
      <span class="sp-p03__snapshot-label">{{ zhCN.p03.snapshotLabel }}</span>
      <span>{{ snapshotNote }}</span>
    </div>

    <section class="sp-p03__kpis" :aria-label="zhCN.p03.title">
      <KpiTile
        v-for="item in kpis"
        :key="item.code"
        :label="item.label"
        :value="item.value"
        :code="item.code"
        :tone="item.tone"
      />
    </section>

    <StateView v-if="loading" state="loading" compact />
    <StateView
      v-else-if="errorText"
      state="error"
      :title="zhCN.p03.loadFailed"
      :description="errorText"
      compact
      @retry="load"
    />

    <template v-else>
      <section class="sp-panel sp-p03__table-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p03.diffTitle }}</span>
            <span v-if="diffs.length" class="sp-panel__count">{{ diffs.length }}</span>
          </div>
          <span class="sp-panel__hint">{{ zhCN.p03.diffHint }}</span>
        </div>
        <StateView
          v-if="!diffs.length"
          state="empty"
          :title="emptyCopy"
          :description="zhCN.p03.emptyHint"
          compact
        />
        <ElTable v-else :data="diffs" size="small" border style="width: 100%">
          <ElTableColumn prop="sku" :label="zhCN.p03.diffColumns.sku" min-width="112" />
          <ElTableColumn :label="zhCN.p03.diffColumns.platform" width="92" align="right">
            <template #default="{ row }">
              <span class="sp-mono">{{ availableText(row.platform_available) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.diffColumns.erp" width="86" align="right">
            <template #default="{ row }">
              <span class="sp-mono">{{ availableText(row.erp_available) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.diffColumns.wms" width="86" align="right">
            <template #default="{ row }">
              <span class="sp-mono">{{ availableText(row.wms_available) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.diffColumns.diffType" width="100">
            <template #default="{ row }">
              <span class="sp-chip" :class="`sp-p03__diff--${row.diff_type}`">
                {{ diffLabel(row.diff_type) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.diffColumns.delta" width="80" align="right">
            <template #default="{ row }">
              <span class="sp-mono">{{ numberText(row.delta) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.diffColumns.tolerance" width="74" align="right">
            <template #default="{ row }">
              <span class="sp-mono">{{ numberText(row.tolerance) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.diffColumns.platformSnapshot" width="130">
            <template #default="{ row }">
              <span class="sp-p03__time">{{ timeText(row.platform_snapshot_at) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.diffColumns.erpSnapshot" width="130">
            <template #default="{ row }">
              <span class="sp-p03__time">{{ timeText(row.erp_snapshot_at) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.diffColumns.wmsSnapshot" width="130">
            <template #default="{ row }">
              <span class="sp-p03__time">{{ timeText(row.wms_snapshot_at) }}</span>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>

      <section class="sp-panel sp-p03__suggestion-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p03.suggestionTitle }}</span>
            <span v-if="suggestions.length" class="sp-panel__count">{{ suggestions.length }}</span>
          </div>
          <div class="sp-p03__suggestion-hint">
            <span>{{ zhCN.p03.suggestionHint }}</span>
            <span class="sp-chip sp-chip--primary">{{ zhCN.p03.suggestionOnly }}</span>
            <StatusBadge v-if="isViewer" :label="zhCN.p03.readonlyHint" tone="neutral" />
          </div>
        </div>
        <StateView
          v-if="!suggestions.length"
          state="empty"
          :title="zhCN.p03.emptySuggestions"
          compact
        />
        <ElTable v-else :data="suggestions" size="small" border style="width: 100%">
          <ElTableColumn prop="sku" :label="zhCN.p03.suggestionColumns.sku" min-width="112" />
          <ElTableColumn :label="zhCN.p03.suggestionColumns.action" width="80">
            <template #default="{ row }">
              <span class="sp-chip">{{ actionLabel(row.action) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.suggestionColumns.quantity" width="76" align="right">
            <template #default="{ row }">
              <span class="sp-mono">{{ numberText(row.quantity) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.suggestionColumns.reason" min-width="240">
            <template #default="{ row }">
              <span class="sp-p03__reason" :title="row.reason">{{ row.reason || zhCN.common.none }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p03.suggestionColumns.status" width="96">
            <template #default="{ row }">
              <StatusBadge
                :label="suggestionStatusLabel(row.status)"
                :tone="suggestionTone(row.status)"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn
            v-if="canHandle"
            :label="zhCN.p03.suggestionColumns.actions"
            width="130"
            fixed="right"
          >
            <template #default="{ row }">
              <div v-if="row.status === 'OPEN'" class="sp-p03__actions">
                <ElButton size="small" @click="openAction(row, 'accept')">
                  {{ zhCN.p03.accept }}
                </ElButton>
                <ElButton size="small" @click="openAction(row, 'ignore')">
                  {{ zhCN.p03.ignore }}
                </ElButton>
              </div>
              <span v-else class="sp-faint">{{ zhCN.common.none }}</span>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>
    </template>

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

.sp-p03__meta {
  margin-left: 5px;
  color: var(--sp-text);
}

.sp-p03__snapshot {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 11px;
  border: 1px solid var(--sp-info-border);
  border-left: 3px solid var(--sp-info);
  border-radius: var(--sp-radius);
  background: var(--sp-info-soft);
  color: var(--sp-info);
  font-size: 11.5px;
}

.sp-p03__snapshot-label {
  flex: none;
  font-weight: 600;
}

.sp-p03__kpis {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.sp-p03__diff--STOCKOUT {
  border-color: var(--sp-danger-border);
  background: var(--sp-danger-soft);
  color: var(--sp-danger);
}
.sp-p03__diff--OVERSELL {
  border-color: var(--sp-warning-border);
  background: var(--sp-warning-soft);
  color: var(--sp-warning);
}
.sp-p03__diff--MISMATCH {
  border-color: var(--sp-info-border);
  background: var(--sp-info-soft);
  color: var(--sp-info);
}
.sp-p03__diff--STAGNANT {
  background: var(--sp-readonly-soft);
  border-color: var(--sp-readonly-border);
  color: var(--sp-readonly);
}
.sp-p03__diff--CONSISTENT {
  border-color: var(--sp-success-border);
  background: var(--sp-success-soft);
  color: var(--sp-success);
}

.sp-p03__time {
  font-size: 10.5px;
  color: var(--sp-muted);
  white-space: nowrap;
}

.sp-p03__reason {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--sp-muted);
}

.sp-p03__suggestion-hint {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-p03__actions {
  display: flex;
  gap: 6px;
}

@media (max-width: 1180px) {
  .sp-p03__kpis {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .sp-p03__kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .sp-p03__suggestion-hint {
    display: none;
  }
}
</style>
