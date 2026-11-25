<script setup lang="ts">
import { computed } from 'vue'
import { ElTable, ElTableColumn } from 'element-plus'

import type { ReportCell, ReportColumn, ReportPayload, ReportRow } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { cellView } from '../utils/format'
import StateView from './StateView.vue'

const props = defineProps<{
  report: ReportPayload
  emptyCopy?: string
}>()

const emit = defineEmits<{
  (event: 'drill', payload: { metricCode: string; label: string }): void
}>()

const rows = computed<ReportRow[]>(() => props.report.rows ?? [])
const columns = computed<ReportColumn[]>(() => props.report.columns ?? [])
const emptyTitle = computed(
  () => props.emptyCopy || props.report.empty_copy || zhCN.states.emptyReport,
)

function cellOf(row: unknown, key: string): ReportCell | undefined {
  return (row as ReportRow).cells?.[key]
}

function cellText(row: unknown, key: string): string {
  return cellView(cellOf(row, key), zhCN.p01.nullBadge).text
}

function cellIsNull(row: unknown, key: string): boolean {
  return cellView(cellOf(row, key), zhCN.p01.nullBadge).isNull
}

function cellTitle(row: unknown, key: string): string {
  const view = cellView(cellOf(row, key), zhCN.p01.nullBadge)
  return view.isNull && view.reason ? zhCN.p01.nullReason(view.reason) : view.text
}

function badgeFor(column: ReportColumn): string {
  return column.additivity === 'RATIO' ? zhCN.p01.ratioBadge : zhCN.p01.nonAdditiveBadge
}

function isNonAdditive(column: ReportColumn): boolean {
  return column.additivity !== 'ADDITIVE'
}

function onCell(column: ReportColumn): void {
  emit('drill', { metricCode: column.key, label: column.label })
}
</script>

<template>
  <ElTable
    :data="rows"
    row-key="stat_date"
    class="sp-data-table"
    border
    scrollbar-always-on
  >
    <ElTableColumn prop="stat_date" :label="zhCN.p01.dateColumn" width="112" fixed>
      <template #header>
        <div class="sp-th">
          <span class="sp-th__label">{{ zhCN.p01.dateColumn }}</span>
        </div>
      </template>
      <template #default="{ row }">
        <span class="sp-date sp-mono">{{ row.stat_date }}</span>
      </template>
    </ElTableColumn>
    <ElTableColumn
      v-for="column in columns"
      :key="column.key"
      :prop="column.key"
      :label="column.label"
      :min-width="column.label.length > 7 ? 148 : 122"
      align="right"
    >
      <template #header>
        <div class="sp-th">
          <span class="sp-th__label">{{ column.label }}</span>
          <span class="sp-th__unit">{{ zhCN.p01.unitValue(column.unit) }}</span>
          <span v-if="isNonAdditive(column)" class="sp-th__badge" :title="badgeFor(column)">
            {{ badgeFor(column) }}
          </span>
        </div>
      </template>
      <template #default="{ row }">
        <button
          type="button"
          class="sp-cell"
          :class="{ 'is-null': cellIsNull(row, column.key) }"
          :title="cellTitle(row, column.key)"
          :aria-label="zhCN.p01.drillCell(column.label)"
          @click="onCell(column)"
        >
          <span class="sp-cell__value">{{ cellText(row, column.key) }}</span>
        </button>
      </template>
    </ElTableColumn>
    <template #empty>
      <StateView state="empty" :title="emptyTitle" :description="zhCN.p01.emptyDescription" compact />
    </template>
  </ElTable>
</template>

<style scoped>
.sp-data-table {
  width: 100%;
}

.sp-date {
  display: inline-block;
  color: var(--sp-muted);
  font-size: 12px;
  white-space: nowrap;
}

.sp-th {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  line-height: 1.3;
  padding: 2px 0;
}

.sp-th__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-th__unit {
  font-size: 10px;
  color: var(--sp-faint);
  font-weight: 400;
}

.sp-th__badge {
  margin-top: 1px;
  padding: 0 4px;
  border: 1px solid var(--sp-warning-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-warning-soft);
  color: var(--sp-warning);
  font-size: 9.5px;
  line-height: 14px;
  font-weight: 500;
}

.sp-cell {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 5px;
  max-width: 100%;
  padding: 2px 4px;
  border: 1px solid transparent;
  border-radius: var(--sp-radius-sm);
  background: transparent;
  font-family: var(--sp-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 12.5px;
  color: var(--sp-text);
  text-align: right;
  white-space: nowrap;
}

.sp-cell:hover,
.sp-cell:focus-visible {
  border-color: var(--sp-primary-soft-strong);
  background: var(--sp-primary-soft);
  color: var(--sp-primary);
}

.sp-cell.is-null {
  font-family: var(--sp-font);
  color: var(--sp-muted);
}

.sp-cell.is-null:hover {
  color: var(--sp-text);
}
</style>
