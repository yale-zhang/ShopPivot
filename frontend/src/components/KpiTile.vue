<script setup lang="ts">
import type { Tone } from '../i18n/zh-CN'

withDefaults(
  defineProps<{
    label: string
    value: number | string
    unit?: string
    hint?: string
    tone?: Tone
    code?: string
  }>(),
  {
    unit: '',
    hint: '',
    tone: 'neutral',
    code: '',
  },
)
</script>

<template>
  <div class="sp-kpi" :class="`sp-kpi--${tone}`">
    <div class="sp-kpi__head">
      <span class="sp-kpi__label">{{ label }}</span>
      <span v-if="code" class="sp-kpi__code sp-mono">{{ code }}</span>
    </div>
    <div class="sp-kpi__value-row">
      <span class="sp-kpi__value sp-mono">{{ value }}</span>
      <span v-if="unit" class="sp-kpi__unit">{{ unit }}</span>
    </div>
    <div v-if="hint" class="sp-kpi__hint">{{ hint }}</div>
  </div>
</template>

<style scoped>
.sp-kpi {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
  padding: 11px 13px 10px;
  overflow: hidden;
  background: var(--sp-surface);
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
}

.sp-kpi::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--sp-readonly);
}

.sp-kpi--success::before {
  background: var(--sp-success);
}
.sp-kpi--warning::before {
  background: var(--sp-warning);
}
.sp-kpi--danger::before {
  background: var(--sp-danger);
}
.sp-kpi--info::before {
  background: var(--sp-info);
}
.sp-kpi--primary::before {
  background: var(--sp-primary);
}

.sp-kpi__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sp-kpi__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11.5px;
  color: var(--sp-muted);
}

.sp-kpi__code {
  flex: none;
  padding: 0 4px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 9px;
  line-height: 14px;
  color: var(--sp-faint);
}

.sp-kpi__value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.sp-kpi__value {
  font-size: 23px;
  font-weight: 600;
  line-height: 1.15;
  letter-spacing: -0.02em;
  color: var(--sp-text);
  font-variant-numeric: tabular-nums;
}

.sp-kpi__unit {
  font-size: 11px;
  color: var(--sp-muted);
}

.sp-kpi__hint {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 10px;
  color: var(--sp-faint);
}
</style>
