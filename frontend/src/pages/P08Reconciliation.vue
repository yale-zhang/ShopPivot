<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElButton, ElTable, ElTableColumn } from 'element-plus'

import { ApiError, fetchSettlementReconciliation } from '../api/client'
import type { SettlementDiff, SettlementReconciliationResponse } from '../api/types'
import { EMPTY_SETTLEMENT_COPY, zhCN, type Tone } from '../i18n/zh-CN'
import { formatDate, formatNumber } from '../utils/format'
import { labelForStatus, toneForStatus } from '../utils/status'
import DrawerPanel from '../components/DrawerPanel.vue'
import KpiTile from '../components/KpiTile.vue'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

interface KpiItem {
  code: string
  label: string
  value: string
  unit: string
  tone: Tone
}

interface DetailField {
  label: string
  value: string
  mono?: boolean
  tone?: Tone
}

const payload = ref<SettlementReconciliationResponse | null>(null)
const loading = ref(true)
const errorText = ref('')
const typeFilter = ref('')
const drawerOpen = ref(false)
const target = ref<SettlementDiff | null>(null)
let requestSeq = 0

const diffs = computed<SettlementDiff[]>(() => payload.value?.diffs ?? [])
const hasDiffs = computed(() => diffs.value.length > 0)
const emptyCopy = computed(() => payload.value?.empty_copy || EMPTY_SETTLEMENT_COPY)
const note = computed(() => payload.value?.note || zhCN.p08.noteFallback)

const windowText = computed(() => {
  const window = payload.value?.window
  if (!window) return ''
  return `${formatDate(window.start)} ~ ${formatDate(window.end)}`
})

const totals = computed(() => payload.value?.totals ?? { expected: 0, settled: 0, delta: 0 })

const filteredDiffs = computed<SettlementDiff[]>(() => {
  if (!typeFilter.value) return diffs.value
  return diffs.value.filter((row) => row.diff_type === typeFilter.value)
})

/** 非 MATCH 的差异条数：一致行不计入差异。 */
const diffCount = computed(
  () => diffs.value.filter((row) => row.diff_type !== 'MATCH').length,
)

const typeTones: Record<string, Tone> = {
  MATCH: 'success',
  AMOUNT_DIFF: 'warning',
  MISSING_SETTLEMENT: 'danger',
  MISSING_ORDER: 'info',
}

function typeLabel(type: string): string {
  return zhCN.p08.typeLabels[type] ?? type
}

function typeChipClass(type: string): string {
  return typeTones[type] ? `sp-p08__type--${type}` : ''
}

function countFor(type: string): number {
  const fromPayload = payload.value?.counts?.[type]
  if (typeof fromPayload === 'number') return fromPayload
  return diffs.value.filter((row) => row.diff_type === type).length
}

const typeOptions = computed(() => [
  { code: '', label: zhCN.p08.filters.all, count: diffs.value.length },
  ...zhCN.p08.typeOptions.map((code) => ({
    code,
    label: typeLabel(code),
    count: countFor(code),
  })),
])

function moneyText(value: number): string {
  if (!Number.isFinite(value)) return zhCN.common.none
  return formatNumber(value, 2)
}

/** 差异为正负带符号；零值保持 0.00。 */
function signedMoney(value: number): string {
  if (!Number.isFinite(value)) return zhCN.common.none
  const formatted = formatNumber(Math.abs(value), 2)
  if (value > 0) return `+${formatted}`
  if (value < 0) return `-${formatted}`
  return formatted
}

/** 金额为空时显示「—」，不得以 0 冒充。 */
function amountText(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return zhCN.common.none
  return formatNumber(value, 2)
}

function deltaTone(value: number): Tone {
  if (value > 0) return 'warning'
  if (value < 0) return 'danger'
  return 'success'
}

function statusLabel(status: string): string {
  return zhCN.p08.statusLabels[status] ?? labelForStatus(status)
}

function statusTone(status: string): Tone {
  return toneForStatus(status)
}

const kpis = computed<KpiItem[]>(() => {
  if (!hasDiffs.value) {
    return [
      { code: 'EXPECTED', label: zhCN.p08.kpi.expected, value: zhCN.common.none, unit: '', tone: 'neutral' },
      { code: 'SETTLED', label: zhCN.p08.kpi.settled, value: zhCN.common.none, unit: '', tone: 'neutral' },
      { code: 'DELTA', label: zhCN.p08.kpi.delta, value: zhCN.common.none, unit: '', tone: 'neutral' },
      { code: 'DIFFS', label: zhCN.p08.kpi.diffs, value: zhCN.common.none, unit: '', tone: 'neutral' },
    ]
  }
  const source = totals.value
  return [
    {
      code: 'EXPECTED',
      label: zhCN.p08.kpi.expected,
      value: moneyText(source.expected),
      unit: zhCN.units.yuan,
      tone: 'neutral',
    },
    {
      code: 'SETTLED',
      label: zhCN.p08.kpi.settled,
      value: moneyText(source.settled),
      unit: zhCN.units.yuan,
      tone: 'info',
    },
    {
      code: 'DELTA',
      label: zhCN.p08.kpi.delta,
      value: signedMoney(source.delta),
      unit: zhCN.units.yuan,
      tone: deltaTone(source.delta),
    },
    {
      code: 'DIFFS',
      label: zhCN.p08.kpi.diffs,
      value: String(diffCount.value),
      unit: '',
      tone: diffCount.value > 0 ? 'danger' : 'success',
    },
  ]
})

const detailFields = computed<DetailField[]>(() => {
  const item = target.value
  if (!item) return []
  const fields = zhCN.p08.drawer.fields
  return [
    { label: fields.orderId, value: item.order_id, mono: true },
    { label: fields.diffType, value: typeLabel(item.diff_type) },
    { label: fields.status, value: statusLabel(item.status) },
    { label: fields.expectedNet, value: moneyText(item.expected_net), mono: true },
    { label: fields.settledAmount, value: amountText(item.settled_amount), mono: true },
    { label: fields.commission, value: amountText(item.commission), mono: true },
    {
      label: fields.delta,
      value: signedMoney(item.delta),
      mono: true,
      tone: deltaTone(item.delta),
    },
    { label: fields.orderRef, value: item.order_ref || zhCN.common.none, mono: true },
    { label: fields.settlementRef, value: item.settlement_ref || zhCN.common.none, mono: true },
  ]
})

function fieldClass(field: DetailField): string[] {
  const classes: string[] = []
  if (field.mono) classes.push('sp-mono')
  if (field.tone) classes.push(`sp-p08__delta--${field.tone}`)
  return classes
}

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError) return cause.userMessage || cause.message || fallback
  if (cause && typeof cause === 'object' && 'userMessage' in cause) {
    return String((cause as { userMessage: unknown }).userMessage) || fallback
  }
  return fallback
}

async function load(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  errorText.value = ''
  try {
    const response = await fetchSettlementReconciliation()
    if (seq !== requestSeq) return
    payload.value = response
  } catch (cause) {
    if (seq !== requestSeq) return
    errorText.value = errorMessage(cause, zhCN.p08.loadFailed)
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function openRow(row: unknown): void {
  target.value = row as SettlementDiff
  drawerOpen.value = true
}

function closeDrawer(): void {
  drawerOpen.value = false
  target.value = null
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="sp-page sp-p08">
    <PageHeader
      :eyebrow="zhCN.p08.eyebrow"
      :title="zhCN.p08.title"
      :description="zhCN.p08.description"
    >
      <template #meta>
        <span v-if="payload?.run_id">
          <span class="sp-faint">{{ zhCN.status.runId }}</span>
          <span class="sp-p08__meta sp-mono">{{ payload.run_id }}</span>
        </span>
        <span v-if="windowText">
          <span class="sp-faint">{{ zhCN.p08.windowLabel }}</span>
          <span class="sp-p08__meta">{{ windowText }}</span>
        </span>
        <StatusBadge :label="zhCN.p08.financeWriteForbidden" tone="danger" />
      </template>
      <template #actions>
        <ElButton size="small" :loading="loading" @click="load">{{ zhCN.p08.refresh }}</ElButton>
      </template>
    </PageHeader>

    <section class="sp-p08__kpis" :aria-label="zhCN.p08.title">
      <KpiTile
        v-for="item in kpis"
        :key="item.code"
        :label="item.label"
        :value="item.value"
        :unit="item.unit"
        :code="item.code"
        :tone="item.tone"
      />
    </section>

    <StateView v-if="loading" state="loading" compact />
    <StateView
      v-else-if="errorText"
      state="error"
      :title="zhCN.p08.loadFailed"
      :description="errorText"
      compact
      @retry="load"
    />

    <template v-else>
      <section class="sp-panel sp-p08__table-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p08.tableTitle }}</span>
            <span v-if="hasDiffs" class="sp-panel__count">{{ filteredDiffs.length }}</span>
          </div>
          <span class="sp-panel__hint">{{ zhCN.p08.tableHint }}</span>
        </div>

        <div class="sp-p08__filter-row">
          <span class="sp-p08__filter-label">{{ zhCN.p08.filters.title }}</span>
          <div class="sp-p08__filters" role="tablist" :aria-label="zhCN.p08.filters.title">
            <button
              v-for="option in typeOptions"
              :key="option.code || 'ALL'"
              type="button"
              class="sp-p08__filter"
              :class="{ 'is-active': typeFilter === option.code }"
              :data-filter="option.code || 'ALL'"
              role="tab"
              :aria-selected="typeFilter === option.code"
              @click="typeFilter = option.code"
            >
              <span>{{ option.label }}</span>
              <span v-if="hasDiffs" class="sp-p08__filter-count sp-mono">{{ option.count }}</span>
            </button>
          </div>
          <span class="sp-p08__filter-hint">{{ zhCN.p08.filters.hint }}</span>
        </div>

        <StateView
          v-if="!hasDiffs"
          state="empty"
          :title="emptyCopy"
          :description="zhCN.p08.emptyHint"
          compact
        />
        <StateView
          v-else-if="!filteredDiffs.length"
          state="empty"
          :title="zhCN.p08.emptyFiltered"
          :description="zhCN.p08.emptyHint"
          compact
        />
        <ElTable
          v-else
          :data="filteredDiffs"
          size="small"
          border
          row-key="order_id"
          style="width: 100%"
          @row-click="openRow"
        >
          <ElTableColumn :label="zhCN.p08.columns.orderId" min-width="132">
            <template #default="{ row }">
              <button
                type="button"
                class="sp-link-btn sp-mono"
                data-open="diff"
                :aria-label="zhCN.p08.openRow"
                @click.stop="openRow(row)"
              >
                {{ row.order_id }}
              </button>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p08.columns.expectedNet" width="128" align="right">
            <template #default="{ row }">
              <span class="sp-mono">{{ moneyText(row.expected_net) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p08.columns.settledAmount" width="120" align="right">
            <template #default="{ row }">
              <span class="sp-mono" :class="{ 'sp-p08__null': row.settled_amount === null }">
                {{ amountText(row.settled_amount) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p08.columns.commission" width="112" align="right">
            <template #default="{ row }">
              <span class="sp-mono" :class="{ 'sp-p08__null': row.commission === null }">
                {{ amountText(row.commission) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p08.columns.delta" width="112" align="right">
            <template #default="{ row }">
              <span class="sp-mono" :class="`sp-p08__delta--${deltaTone(row.delta)}`">
                {{ signedMoney(row.delta) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p08.columns.diffType" width="116">
            <template #default="{ row }">
              <span class="sp-chip" :class="typeChipClass(row.diff_type)">
                {{ typeLabel(row.diff_type) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p08.columns.orderRef" min-width="150">
            <template #default="{ row }">
              <span class="sp-p08__ref sp-mono" :title="row.order_ref">
                {{ row.order_ref || zhCN.common.none }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p08.columns.settlementRef" min-width="150">
            <template #default="{ row }">
              <span class="sp-p08__ref sp-mono" :title="row.settlement_ref">
                {{ row.settlement_ref || zhCN.common.none }}
              </span>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>
    </template>

    <div class="sp-p08__note" role="note">
      <span class="sp-p08__note-label">{{ zhCN.p08.noteLabel }}</span>
      <span class="sp-p08__note-text">{{ note }}</span>
    </div>

    <DrawerPanel
      :open="drawerOpen"
      :title="zhCN.p08.drawer.title"
      :subtitle="target ? target.order_id : zhCN.p08.drawer.subtitle"
      width="600px"
      :close-label="zhCN.p08.drawer.close"
      @close="closeDrawer"
    >
      <div v-if="target" class="sp-p08__detail">
        <div class="sp-p08__detail-head">
          <span class="sp-mono sp-p08__detail-no">{{ target.order_id }}</span>
          <span class="sp-chip" :class="typeChipClass(target.diff_type)">
            {{ typeLabel(target.diff_type) }}
          </span>
          <StatusBadge
            :label="statusLabel(target.status)"
            :tone="statusTone(target.status)"
            dot
          />
        </div>

        <section class="sp-p08__sub">
          <h3>{{ zhCN.p08.drawer.summary }}</h3>
          <dl class="sp-p08__kv">
            <template v-for="field in detailFields" :key="field.label">
              <dt>{{ field.label }}</dt>
              <dd :class="fieldClass(field)">{{ field.value }}</dd>
            </template>
          </dl>
        </section>

        <section class="sp-p08__sub">
          <h3>{{ zhCN.p08.drawer.totals }}</h3>
          <dl class="sp-p08__kv">
            <dt>{{ zhCN.p08.drawer.totalsFields.expected }}</dt>
            <dd class="sp-mono">{{ moneyText(totals.expected) }}</dd>
            <dt>{{ zhCN.p08.drawer.totalsFields.settled }}</dt>
            <dd class="sp-mono">{{ moneyText(totals.settled) }}</dd>
            <dt>{{ zhCN.p08.drawer.totalsFields.delta }}</dt>
            <dd class="sp-mono" :class="`sp-p08__delta--${deltaTone(totals.delta)}`">
              {{ signedMoney(totals.delta) }}
            </dd>
          </dl>
        </section>

        <p class="sp-p08__drawer-note">{{ zhCN.p08.drawer.note }}</p>
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

.sp-p08__meta {
  margin-left: 5px;
  color: var(--sp-text);
}

.sp-p08__kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.sp-p08__table-panel {
  overflow: hidden;
}

.sp-p08__table-panel :deep(.el-table__row) {
  cursor: pointer;
}

.sp-p08__filter-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  padding: 9px 14px;
  border-bottom: 1px solid var(--sp-border);
  background: var(--sp-bg);
}

.sp-p08__filter-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-p08__filters {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  padding: 2px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
}

.sp-p08__filter {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 25px;
  padding: 0 8px;
  border: 0;
  border-radius: var(--sp-radius-sm);
  background: transparent;
  font-size: 11.5px;
  color: var(--sp-muted);
}

.sp-p08__filter:hover {
  background: var(--sp-surface-sunken);
  color: var(--sp-text);
}

.sp-p08__filter.is-active {
  background: var(--sp-primary-soft);
  color: var(--sp-primary);
  font-weight: 600;
}

.sp-p08__filter-count {
  padding: 0 4px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-pill);
  background: var(--sp-surface);
  font-size: 9.5px;
  line-height: 14px;
  color: var(--sp-faint);
}

.sp-p08__filter.is-active .sp-p08__filter-count {
  border-color: var(--sp-primary-soft-strong);
  color: var(--sp-primary);
}

.sp-p08__filter-hint {
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-p08__null {
  color: var(--sp-faint);
}

.sp-p08__ref {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: var(--sp-muted);
}

.sp-p08__delta--success {
  color: var(--sp-success);
}

.sp-p08__delta--warning {
  color: var(--sp-warning);
}

.sp-p08__delta--danger {
  color: var(--sp-danger);
}

.sp-p08__type--MATCH {
  border-color: var(--sp-success-border);
  background: var(--sp-success-soft);
  color: var(--sp-success);
}

.sp-p08__type--AMOUNT_DIFF {
  border-color: var(--sp-warning-border);
  background: var(--sp-warning-soft);
  color: var(--sp-warning);
}

.sp-p08__type--MISSING_SETTLEMENT {
  border-color: var(--sp-danger-border);
  background: var(--sp-danger-soft);
  color: var(--sp-danger);
}

.sp-p08__type--MISSING_ORDER {
  border-color: var(--sp-info-border);
  background: var(--sp-info-soft);
  color: var(--sp-info);
}

.sp-p08__note {
  position: sticky;
  bottom: 6px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  z-index: 5;
  padding: 8px 12px;
  border: 1px solid var(--sp-danger-border);
  border-left: 3px solid var(--sp-danger);
  border-radius: var(--sp-radius);
  background: var(--sp-danger-soft);
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--sp-danger);
}

.sp-p08__note-label {
  flex: none;
  font-weight: 600;
}

.sp-p08__note-text {
  color: var(--sp-text);
}

.sp-p08__detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p08__detail-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.sp-p08__detail-no {
  font-size: 13px;
  font-weight: 600;
}

.sp-p08__sub {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sp-p08__sub h3 {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--sp-muted);
}

.sp-p08__kv {
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: 4px 10px;
  padding: 9px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 12px;
}

.sp-p08__kv dt {
  color: var(--sp-muted);
}

.sp-p08__kv dd {
  min-width: 0;
  word-break: break-word;
}

.sp-p08__drawer-note {
  padding: 8px 10px;
  border: 1px solid var(--sp-danger-border);
  border-left: 3px solid var(--sp-danger);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-danger-soft);
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--sp-text);
}

@media (max-width: 1080px) {
  .sp-p08__kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .sp-p08__kpis {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
