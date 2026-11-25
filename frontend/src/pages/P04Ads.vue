<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElButton, ElTable, ElTableColumn } from 'element-plus'

import { ApiError, fetchAdsSummary } from '../api/client'
import type { AdsCampaign, AdsSummaryResponse } from '../api/types'
import { zhCN, type Tone } from '../i18n/zh-CN'
import { formatDate, formatNumber } from '../utils/format'
import KpiTile from '../components/KpiTile.vue'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

const payload = ref<AdsSummaryResponse | null>(null)
const loading = ref(true)
const errorText = ref('')
let requestSeq = 0

const campaigns = computed<AdsCampaign[]>(() => payload.value?.campaigns ?? [])
const hasData = computed(() => campaigns.value.length > 0)
const emptyCopy = computed(() => payload.value?.empty_copy || zhCN.p04.empty)
const note = computed(() => payload.value?.note || zhCN.p04.noteFallback)

const windowText = computed(() => {
  const window = payload.value?.window
  if (!window) return ''
  return `${formatDate(window.start)} ~ ${formatDate(window.end)}`
})

const totals = computed(() => {
  const source = payload.value?.totals
  if (source) return source
  const cost = campaigns.value.reduce((sum, row) => sum + row.cost, 0)
  const revenue = campaigns.value.reduce((sum, row) => sum + row.revenue, 0)
  return { cost, revenue, roi: cost > 0 ? revenue / cost : null }
})

/** 投产比为空时显示「不适用」，不得显示 0。 */
function roiText(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return zhCN.common.notAvailable
  }
  return value.toFixed(2)
}

function moneyText(value: number): string {
  return formatNumber(value, 2)
}

function alertLabel(level: string): string {
  return zhCN.p04.alertLevels[level] ?? level
}

function alertTone(level: string): Tone {
  if (level === 'ALERT') return 'danger'
  if (level === 'WATCH') return 'warning'
  if (level === 'OK') return 'success'
  return 'neutral'
}

function countFor(level: string): number {
  const fromPayload = payload.value?.counts?.[level]
  if (typeof fromPayload === 'number') return fromPayload
  return campaigns.value.filter((row) => row.alert_level === level).length
}

const alertCount = computed(() => countFor('ALERT') + countFor('WATCH'))

const kpis = computed(() => {
  if (!hasData.value) {
    return [
      { code: 'COST', label: zhCN.p04.kpi.cost, value: zhCN.common.none, unit: '', tone: 'neutral' as Tone },
      { code: 'REVENUE', label: zhCN.p04.kpi.revenue, value: zhCN.common.none, unit: '', tone: 'neutral' as Tone },
      { code: 'ROI', label: zhCN.p04.kpi.roi, value: zhCN.common.notAvailable, unit: '', tone: 'neutral' as Tone },
      { code: 'ALERT', label: zhCN.p04.kpi.alert, value: zhCN.common.none, unit: '', tone: 'neutral' as Tone },
    ]
  }
  const source = totals.value
  return [
    {
      code: 'COST',
      label: zhCN.p04.kpi.cost,
      value: moneyText(source.cost),
      unit: zhCN.units.yuan,
      tone: 'neutral' as Tone,
    },
    {
      code: 'REVENUE',
      label: zhCN.p04.kpi.revenue,
      value: moneyText(source.revenue),
      unit: zhCN.units.yuan,
      tone: 'info' as Tone,
    },
    {
      code: 'ROI',
      label: zhCN.p04.kpi.roi,
      value: roiText(source.roi),
      unit: '',
      tone: 'primary' as Tone,
    },
    {
      code: 'ALERT',
      label: zhCN.p04.kpi.alert,
      value: String(alertCount.value),
      unit: '',
      tone: (alertCount.value > 0 ? 'danger' : 'success') as Tone,
    },
  ]
})

const barMax = computed(() => {
  let max = 0
  for (const row of campaigns.value) {
    max = Math.max(max, row.cost, row.revenue)
  }
  return max
})

function barWidth(value: number): string {
  if (!barMax.value || barMax.value <= 0) return '0%'
  const ratio = Math.min(1, Math.max(0, value / barMax.value))
  return `${Math.max(2, ratio * 100)}%`
}

function barAria(row: AdsCampaign): string {
  return zhCN.p04.barAria(row.campaign, moneyText(row.cost), moneyText(row.revenue))
}

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError) return cause.userMessage || fallback
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
    const response = await fetchAdsSummary()
    if (seq !== requestSeq) return
    payload.value = response
  } catch (cause) {
    if (seq !== requestSeq) return
    errorText.value = errorMessage(cause, zhCN.p04.loadFailed)
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="sp-page sp-p04">
    <PageHeader
      :eyebrow="zhCN.p04.eyebrow"
      :title="zhCN.p04.title"
      :description="zhCN.p04.description"
    >
      <template #meta>
        <span v-if="payload?.run_id">
          <span class="sp-faint">{{ zhCN.status.runId }}</span>
          <span class="sp-p04__meta sp-mono">{{ payload.run_id }}</span>
        </span>
        <span v-if="windowText">
          <span class="sp-faint">{{ zhCN.context.window }}</span>
          <span class="sp-p04__meta">{{ windowText }}</span>
        </span>
      </template>
      <template #actions>
        <ElButton size="small" :loading="loading" @click="load">{{ zhCN.p04.refresh }}</ElButton>
      </template>
    </PageHeader>

    <section class="sp-p04__kpis" :aria-label="zhCN.p04.title">
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
      :title="zhCN.p04.loadFailed"
      :description="errorText"
      compact
      @retry="load"
    />

    <template v-else>
      <section v-if="hasData" class="sp-panel sp-p04__bars-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">{{ zhCN.p04.barTitle }}</div>
          <span class="sp-panel__hint">{{ zhCN.p04.barHint }}</span>
        </div>
        <div class="sp-p04__bars-body">
          <div
            v-for="row in campaigns"
            :key="`bar-${row.campaign}`"
            class="sp-p04__bar-row"
            role="img"
            :aria-label="barAria(row)"
          >
            <div class="sp-p04__bar-name">{{ row.campaign }}</div>
            <div class="sp-p04__bar-line">
              <span class="sp-p04__bar-label">{{ zhCN.p04.barCost }}</span>
              <div class="sp-p04__bar-track">
                <div
                  class="sp-p04__bar sp-p04__bar--cost"
                  :style="{ width: barWidth(row.cost) }"
                />
              </div>
              <span class="sp-p04__bar-value sp-mono">{{ moneyText(row.cost) }}</span>
            </div>
            <div class="sp-p04__bar-line">
              <span class="sp-p04__bar-label">{{ zhCN.p04.barRevenue }}</span>
              <div class="sp-p04__bar-track">
                <div
                  class="sp-p04__bar sp-p04__bar--revenue"
                  :style="{ width: barWidth(row.revenue) }"
                />
              </div>
              <span class="sp-p04__bar-value sp-mono">{{ moneyText(row.revenue) }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="sp-panel sp-p04__table-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p04.tableTitle }}</span>
            <span v-if="campaigns.length" class="sp-panel__count">{{ campaigns.length }}</span>
          </div>
          <span class="sp-panel__hint">{{ zhCN.p04.tableHint }}</span>
        </div>
        <StateView
          v-if="!campaigns.length"
          state="empty"
          :title="emptyCopy"
          :description="zhCN.p04.emptyHint"
          compact
        />
        <ElTable v-else :data="campaigns" size="small" border style="width: 100%">
          <ElTableColumn :label="zhCN.p04.columns.campaign" min-width="150">
            <template #default="{ row }">
              <span class="sp-p04__campaign" :title="row.campaign">{{ row.campaign }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p04.columns.cost" width="120" align="right">
            <template #default="{ row }">
              <span class="sp-mono">{{ moneyText(row.cost) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p04.columns.revenue" width="120" align="right">
            <template #default="{ row }">
              <span class="sp-mono">{{ moneyText(row.revenue) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p04.columns.roi" width="96" align="right">
            <template #default="{ row }">
              <span class="sp-mono" :class="{ 'is-not-applicable': row.roi === null }">
                {{ roiText(row.roi) }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p04.columns.alertLevel" width="102">
            <template #default="{ row }">
              <StatusBadge :label="alertLabel(row.alert_level)" :tone="alertTone(row.alert_level)" />
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p04.columns.suggestion" min-width="240">
            <template #default="{ row }">
              <span class="sp-p04__suggestion" :title="row.suggestion">
                {{ row.suggestion || zhCN.common.none }}
              </span>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>
    </template>

    <div class="sp-p04__note" role="note">
      <span class="sp-p04__note-label">{{ zhCN.p04.noteLabel }}</span>
      <span class="sp-p04__note-text">{{ note }}</span>
    </div>
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p04__meta {
  margin-left: 5px;
  color: var(--sp-text);
}

.sp-p04__kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.sp-p04__bars-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 11px 14px 13px;
}

.sp-p04__bar-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--sp-border);
}

.sp-p04__bar-row:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.sp-p04__bar-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-p04__bar-line {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) 96px;
  align-items: center;
  gap: 8px;
}

.sp-p04__bar-label {
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-p04__bar-track {
  height: 9px;
  overflow: hidden;
  background: var(--sp-surface-sunken);
  border-radius: var(--sp-radius-sm);
}

.sp-p04__bar {
  height: 100%;
  border-radius: var(--sp-radius-sm);
  transition: width 160ms ease;
}

.sp-p04__bar--cost {
  background: var(--sp-warning);
}

.sp-p04__bar--revenue {
  background: var(--sp-primary);
}

.sp-p04__bar-value {
  text-align: right;
  font-size: 11px;
  color: var(--sp-text);
  font-variant-numeric: tabular-nums;
}

.sp-p04__table-panel {
  overflow: hidden;
}

.sp-p04__campaign {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--sp-text);
}

.sp-p04__suggestion {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--sp-muted);
}

.sp-p04__note {
  position: sticky;
  bottom: 6px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  z-index: 5;
  padding: 8px 12px;
  border: 1px solid var(--sp-info-border);
  border-left: 3px solid var(--sp-info);
  border-radius: var(--sp-radius);
  background: var(--sp-info-soft);
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--sp-info);
}

.sp-p04__note-label {
  flex: none;
  font-weight: 600;
}

.sp-p04__note-text {
  color: var(--sp-text);
}

.is-not-applicable {
  color: var(--sp-faint);
}

@media (max-width: 1080px) {
  .sp-p04__kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .sp-p04__kpis {
    grid-template-columns: minmax(0, 1fr);
  }
  .sp-p04__bar-line {
    grid-template-columns: 34px minmax(0, 1fr) 82px;
  }
}
</style>
