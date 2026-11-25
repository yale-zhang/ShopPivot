<script setup lang="ts">
import type { ReviewTrendPoint } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { formatMonthDay } from '../utils/format'

const props = withDefaults(
  defineProps<{
    points: ReviewTrendPoint[]
    maxScale?: number
  }>(),
  { maxScale: 5 },
)

function dsrText(dsr: number | null): string {
  return dsr === null || dsr === undefined || Number.isNaN(dsr) ? zhCN.common.none : dsr.toFixed(2)
}

function barHeight(dsr: number | null): string {
  if (dsr === null || dsr === undefined || Number.isNaN(dsr)) return '0%'
  const ratio = Math.min(1, Math.max(0, dsr / props.maxScale))
  return `${Math.max(4, ratio * 100)}%`
}

function pointTitle(point: ReviewTrendPoint): string {
  return zhCN.p02.trend.pointTitle(point.stat_date, dsrText(point.dsr), point.count)
}
</script>

<template>
  <div class="sp-trend" role="img" :aria-label="zhCN.p02.trend.aria(points.length)">
    <div v-for="point in points" :key="point.stat_date" class="sp-trend__col" :title="pointTitle(point)">
      <span class="sp-trend__value sp-mono">{{ dsrText(point.dsr) }}</span>
      <div class="sp-trend__track">
        <div class="sp-trend__bar" :style="{ height: barHeight(point.dsr) }" />
      </div>
      <span class="sp-trend__date sp-mono">{{ formatMonthDay(point.stat_date) }}</span>
      <span class="sp-trend__count">{{ zhCN.p02.trend.sample(point.count) }}</span>
    </div>
  </div>
</template>

<style scoped>
.sp-trend {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  min-height: 174px;
  padding: 10px 12px 8px;
  overflow-x: auto;
  background: var(--sp-surface);
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
}

.sp-trend__col {
  display: flex;
  flex: 1 0 46px;
  min-width: 46px;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  height: 156px;
}

.sp-trend__value {
  font-size: 11px;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-trend__track {
  display: flex;
  align-items: flex-end;
  width: 100%;
  max-width: 34px;
  flex: 1;
  min-height: 0;
  background: var(--sp-surface-sunken);
  border-radius: var(--sp-radius-sm);
}

.sp-trend__bar {
  width: 100%;
  min-height: 2px;
  background: var(--sp-primary);
  border-radius: var(--sp-radius-sm) var(--sp-radius-sm) 0 0;
  transition: height 160ms ease;
}

.sp-trend__col:hover .sp-trend__bar {
  background: var(--sp-primary-hover);
}

.sp-trend__date {
  font-size: 9.5px;
  color: var(--sp-muted);
}

.sp-trend__count {
  font-size: 9px;
  color: var(--sp-faint);
  white-space: nowrap;
}
</style>
