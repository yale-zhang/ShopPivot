<script setup lang="ts">
import type { TimelineEntry } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { formatDateTime } from '../utils/format'
import { labelForStatus, toneForStatus } from '../utils/status'

function showExtraLabel(state: string, label: string): boolean {
  return Boolean(label) && label !== labelForStatus(state)
}
import StatusBadge from './StatusBadge.vue'

defineProps<{
  entries: TimelineEntry[]
}>()
</script>

<template>
  <div class="sp-timeline">
    <ol v-if="entries.length" class="sp-timeline__list">
      <li v-for="(entry, index) in entries" :key="`${entry.state}-${index}`" class="sp-timeline__item">
        <span
          class="sp-timeline__dot"
          :class="`sp-timeline__dot--${toneForStatus(entry.state)}`"
          aria-hidden="true"
        />
        <div class="sp-timeline__content">
          <div class="sp-timeline__head">
            <StatusBadge :label="labelForStatus(entry.state)" :tone="toneForStatus(entry.state)" />
            <span v-if="showExtraLabel(entry.state, entry.label)" class="sp-timeline__label">{{ entry.label }}</span>
          </div>
          <div class="sp-timeline__time sp-mono">
            {{ formatDateTime(entry.at) || zhCN.common.none }}
          </div>
        </div>
      </li>
    </ol>
    <p v-else class="sp-timeline__empty">{{ zhCN.p06.timeline.empty }}</p>
  </div>
</template>

<style scoped>
.sp-timeline__list {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-left: 4px;
}

.sp-timeline__item {
  position: relative;
  display: flex;
  gap: 10px;
  padding: 7px 0 7px 0;
}

.sp-timeline__item:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 22px;
  bottom: -5px;
  width: 1px;
  background: var(--sp-border);
}

.sp-timeline__dot {
  width: 9px;
  height: 9px;
  margin-top: 5px;
  border: 2px solid var(--sp-border-strong);
  border-radius: 50%;
  background: var(--sp-surface);
  flex: none;
  z-index: 1;
}

.sp-timeline__dot--success { border-color: var(--sp-success); }
.sp-timeline__dot--warning { border-color: var(--sp-warning); }
.sp-timeline__dot--danger { border-color: var(--sp-danger); }
.sp-timeline__dot--info { border-color: var(--sp-info); }
.sp-timeline__dot--primary { border-color: var(--sp-primary); }

.sp-timeline__content {
  min-width: 0;
}

.sp-timeline__head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}

.sp-timeline__label {
  font-size: 12.5px;
  color: var(--sp-text);
}

.sp-timeline__time {
  margin-top: 1px;
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-timeline__empty {
  font-size: 12px;
  color: var(--sp-muted);
  padding: 6px 0;
}
</style>
