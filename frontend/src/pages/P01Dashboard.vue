<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { ApiError, fetchLatestReport } from '../api/client'
import type { ReportPayload } from '../api/types'
import { EMPTY_REPORT_COPY, zhCN } from '../i18n/zh-CN'
import { useContextStore } from '../stores/context'
import { formatDateTime } from '../utils/format'
import { labelForStatus, toneForStatus } from '../utils/status'
import DataTable from '../components/DataTable.vue'
import DrilldownDrawer from '../components/DrilldownDrawer.vue'
import ExportButton from '../components/ExportButton.vue'
import MetricCard from '../components/MetricCard.vue'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

const context = useContextStore()

const report = ref<ReportPayload | null>(null)
const loading = ref(true)
const errorText = ref('')
const drawerOpen = ref(false)
const activeMetric = ref<string | null>(null)
const activeLabel = ref('')
let requestSeq = 0

const isEmpty = computed(() => {
  const value = report.value
  if (!value) return true
  return value.data_state === 'EMPTY' || value.report_id === null || value.rows.length === 0
})

const latestRow = computed(() => {
  const rows = report.value?.rows ?? []
  return rows.length ? rows[rows.length - 1] : null
})

const columnsByKey = computed(() => {
  const map = new Map<string, ReportPayload['columns'][number]>()
  for (const column of report.value?.columns ?? []) map.set(column.key, column)
  return map
})

const metricCards = computed(() => {
  const definitions = [
    { code: 'uv', label: zhCN.p01.metricNames.uv, unit: zhCN.p01.metricUnits.uv },
    { code: 'paid_orders', label: zhCN.p01.metricNames.paid_orders, unit: zhCN.p01.metricUnits.paid_orders },
    { code: 'gmv', label: zhCN.p01.metricNames.gmv, unit: zhCN.p01.metricUnits.gmv },
    { code: 'cvr', label: zhCN.p01.metricNames.cvr, unit: zhCN.p01.metricUnits.cvr },
  ]
  return definitions.map((definition) => {
    const column = columnsByKey.value.get(definition.code)
    const cell = latestRow.value?.cells?.[definition.code]
    const isNull = !cell || cell.raw === null || cell.null_reason !== null
    return {
      code: definition.code,
      label: column?.label || definition.label,
      unit: column?.unit || definition.unit,
      value: isNull ? null : cell.value,
      nullReason: cell?.null_reason ?? null,
      latestDate: latestRow.value?.stat_date ?? '',
    }
  })
})

const emptyTitle = computed(() => report.value?.empty_copy || EMPTY_REPORT_COPY)

const metaWindow = computed(() => report.value?.window_label || context.window || zhCN.common.none)
const metaVersion = computed(() => report.value?.metric_version || context.metricVersion || zhCN.common.none)

async function loadReport(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  errorText.value = ''
  report.value = null
  drawerOpen.value = false
  try {
    await context.ensureLoaded()
    if (!context.platform || !context.shopId) {
      loading.value = false
      return
    }
    const payload = await fetchLatestReport({
      platform: context.platform,
      shopId: context.shopId,
      window: context.window,
      metricVersion: context.metricVersion,
    })
    if (seq !== requestSeq) return
    report.value = payload
  } catch (cause) {
    if (seq !== requestSeq) return
    errorText.value =
      cause instanceof ApiError
        ? cause.userMessage
        : cause && typeof cause === 'object' && 'userMessage' in cause
          ? String((cause as { userMessage: unknown }).userMessage)
          : zhCN.p01.loadFailed
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function openDrill(metricCode: string, label?: string): void {
  activeMetric.value = metricCode
  activeLabel.value = label || columnsByKey.value.get(metricCode)?.label || metricCode
  drawerOpen.value = true
}

watch(
  () => [context.platform, context.shopId, context.window, context.metricVersion] as const,
  () => {
    void loadReport()
  },
)

onMounted(() => {
  void loadReport()
})
</script>

<template>
  <div class="sp-page sp-p01">
    <PageHeader
      :eyebrow="zhCN.p01.eyebrow"
      :title="zhCN.p01.title"
      :description="zhCN.p01.description"
    >
      <template #meta>
        <span>
          <span class="sp-faint">{{ zhCN.p01.windowLabel }}</span>
          <span class="sp-p01__meta-value">{{ metaWindow }}</span>
        </span>
        <span>
          <span class="sp-faint">{{ zhCN.p01.metricVersion }}</span>
          <span class="sp-p01__meta-value sp-mono">{{ metaVersion }}</span>
        </span>
        <span v-if="report?.generated_at">
          <span class="sp-faint">{{ zhCN.p01.generatedAt }}</span>
          <span class="sp-p01__meta-value">{{ formatDateTime(report?.generated_at) }}</span>
        </span>
        <span v-if="report?.report_id">
          <span class="sp-faint">{{ zhCN.p01.reportId }}</span>
          <span class="sp-p01__meta-value sp-mono">{{ report.report_id }}</span>
        </span>
      </template>
      <template #actions>
        <ExportButton :report-id="report?.report_id ?? null" :watermark="report?.watermark ?? ''" />
      </template>
    </PageHeader>

    <StateView v-if="loading" state="loading" :description="zhCN.p01.tableHint" />

    <StateView
      v-else-if="errorText"
      state="error"
      :title="zhCN.p01.loadFailed"
      :description="errorText"
      @retry="loadReport"
    />

    <StateView
      v-else-if="isEmpty"
      state="empty"
      :title="emptyTitle"
      :description="zhCN.p01.emptyDescription"
    />

    <template v-else-if="report">
      <section class="sp-report-meta" :aria-label="zhCN.p01.tableTitle">
        <div class="sp-report-meta__watermark">
          <span class="sp-report-meta__label">{{ zhCN.p01.watermark }}</span>
          <span class="sp-report-meta__watermark-text" :title="report.watermark">
            {{ report.watermark || zhCN.common.none }}
          </span>
        </div>
        <div class="sp-report-meta__items">
          <div class="sp-report-meta__item">
            <span class="sp-report-meta__label">{{ zhCN.p01.channel }}</span>
            <span class="sp-report-meta__value">{{ report.channel_label || report.channel || zhCN.common.none }}</span>
          </div>
          <div class="sp-report-meta__item">
            <span class="sp-report-meta__label">{{ zhCN.p01.dataState }}</span>
            <StatusBadge
              :label="labelForStatus(report.data_state)"
              :tone="toneForStatus(report.data_state)"
              dot
            />
          </div>
          <div class="sp-report-meta__item">
            <span class="sp-report-meta__label">{{ zhCN.p01.windowLabel }}</span>
            <span class="sp-report-meta__value">{{ report.window_label || metaWindow }}</span>
          </div>
          <div class="sp-report-meta__item">
            <span class="sp-report-meta__label">{{ zhCN.p01.gateMax }}</span>
            <span class="sp-report-meta__value sp-mono">{{ report.gate_level_max || context.platformGateMax || zhCN.common.none }}</span>
          </div>
        </div>
      </section>

      <section v-if="report.alerts.length" class="sp-alerts" role="alert">
        <div class="sp-alerts__head">
          <span class="sp-alerts__title">{{ zhCN.p01.alertsTitle }}</span>
          <span class="sp-alerts__hint">{{ zhCN.p01.alertsHint }}</span>
        </div>
        <ul class="sp-alerts__list">
          <li v-for="(alert, index) in report.alerts" :key="`${alert.metric_code}-${index}`">
            <button
              type="button"
              class="sp-alerts__item"
              @click="openDrill(alert.metric_code)"
            >
              <span class="sp-chip sp-chip--primary">{{ alert.metric_code }}</span>
              <span class="sp-alerts__message">{{ alert.message }}</span>
            </button>
          </li>
        </ul>
      </section>

      <section class="sp-p01__metrics">
        <div class="sp-p01__section-head">
          <h2 class="sp-p01__section-title">{{ zhCN.p01.metricsTitle }}</h2>
          <span class="sp-p01__section-hint">{{ zhCN.p01.metricsHint }}</span>
        </div>
        <div class="sp-p01__metric-grid">
          <MetricCard
            v-for="metric in metricCards"
            :key="metric.code"
            :metric-code="metric.code"
            :label="metric.label"
            :value="metric.value"
            :unit="metric.unit"
            :null-reason="metric.nullReason"
            :latest-date="metric.latestDate"
            @select="openDrill(metric.code, metric.label)"
          />
        </div>
      </section>

      <section class="sp-panel sp-p01__table-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p01.tableTitle }}</span>
            <span class="sp-panel__count">{{ report.rows.length }}</span>
          </div>
          <div class="sp-p01__table-hint">
            <span class="sp-p01__scroll-hint">{{ zhCN.p01.tableScrollHint }}</span>
            <span class="sp-faint">{{ zhCN.p01.drillChain }}</span>
            <span v-if="report.drill" class="sp-mono">{{ report.drill }}</span>
          </div>
        </div>
        <div class="sp-p01__table">
          <DataTable :report="report" @drill="openDrill($event.metricCode, $event.label)" />
        </div>
      </section>
    </template>

    <DrilldownDrawer
      v-model:open="drawerOpen"
      :metric-code="activeMetric"
      :metric-label="activeLabel"
      :run-id="report?.run_id ?? null"
    />
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p01__meta-value {
  margin-left: 5px;
  color: var(--sp-text);
}

.sp-report-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 12px;
  background: var(--sp-surface);
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
}

.sp-report-meta__watermark {
  display: flex;
  align-items: baseline;
  gap: 7px;
  min-width: 0;
  flex: 1;
}

.sp-report-meta__label {
  flex: none;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--sp-faint);
}

.sp-report-meta__watermark-text {
  min-width: 0;
  font-family: var(--sp-font-mono);
  font-size: 10.5px;
  line-height: 1.45;
  color: var(--sp-muted);
  overflow-wrap: anywhere;
}

.sp-report-meta__items {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 16px;
  flex: none;
}

.sp-report-meta__item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.sp-report-meta__value {
  font-size: 11.5px;
  color: var(--sp-text);
}

.sp-alerts {
  padding: 9px 12px;
  background: var(--sp-warning-soft);
  border: 1px solid var(--sp-warning-border);
  border-left: 3px solid var(--sp-warning);
  border-radius: var(--sp-radius);
}

.sp-alerts__head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
}

.sp-alerts__title {
  font-size: 12px;
  font-weight: 600;
  color: var(--sp-warning);
}

.sp-alerts__hint {
  font-size: 10.5px;
  color: #7a5a24;
}

.sp-alerts__list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 4px;
}

.sp-alerts__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 2px 0;
  border: 0;
  background: transparent;
  text-align: left;
  font-size: 12px;
  color: var(--sp-text);
}

.sp-alerts__item:hover .sp-alerts__message {
  color: var(--sp-warning);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.sp-alerts__message {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sp-p01__metrics {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.sp-p01__section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.sp-p01__section-title {
  font-size: 12.5px;
  font-weight: 650;
  color: var(--sp-text);
}

.sp-p01__section-hint {
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-p01__metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.sp-p01__table-panel {
  overflow: hidden;
}

.sp-panel__count {
  padding: 0 5px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-pill);
  background: var(--sp-surface);
  font-family: var(--sp-font-mono);
  font-size: 9.5px;
  font-weight: 500;
  line-height: 15px;
  color: var(--sp-muted);
}

.sp-p01__table-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
}

.sp-p01__scroll-hint {
  padding-right: 8px;
  border-right: 1px solid var(--sp-border);
  color: var(--sp-faint);
}

.sp-p01__table {
  background: var(--sp-surface);
}

@media (max-width: 1180px) {
  .sp-p01__metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .sp-report-meta {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
  }
  .sp-report-meta__items {
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  .sp-p01__metric-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .sp-p01__table-hint {
    display: none;
  }
}
</style>
