<script setup lang="ts">
import { computed } from 'vue'

import { zhCN } from '../i18n/zh-CN'

const props = withDefaults(
  defineProps<{
    metricCode: string
    label: string
    value: string | null | undefined
    unit?: string
    nullReason?: string | null
    latestDate?: string
    clickable?: boolean
  }>(),
  { clickable: true },
)

const emit = defineEmits<{ (event: 'select', metricCode: string): void }>()

const isNull = computed(
  () =>
    props.value === null ||
    props.value === undefined ||
    props.value === '' ||
    props.nullReason !== null && props.nullReason !== undefined,
)

const displayValue = computed(() => (isNull.value ? zhCN.p01.metricNull : String(props.value)))

const ariaLabel = computed(() =>
  isNull.value
    ? `${props.label}：${zhCN.p01.metricNull}${props.nullReason ? `，${zhCN.p01.nullReason(props.nullReason)}` : ''}`
    : `${props.label}：${displayValue.value}${props.unit ?? ''}`,
)

function onClick(): void {
  if (props.clickable !== false) emit('select', props.metricCode)
}
</script>

<template>
  <button
    type="button"
    class="sp-metric-card"
    :class="{ 'is-null': isNull, 'is-static': clickable === false }"
    :aria-label="ariaLabel"
    :disabled="clickable === false"
    @click="onClick"
  >
    <span class="sp-metric-card__head">
      <span class="sp-metric-card__label">{{ label }}</span>
      <span class="sp-metric-card__code">{{ metricCode }}</span>
    </span>
    <span class="sp-metric-card__value-row">
      <span class="sp-metric-card__value" :class="{ 'is-null': isNull }">{{ displayValue }}</span>
      <span v-if="!isNull && unit" class="sp-metric-card__unit">{{ unit }}</span>
    </span>
    <span class="sp-metric-card__foot">
      <span v-if="isNull && nullReason" class="sp-metric-card__reason">
        {{ zhCN.p01.nullReason(nullReason) }}
      </span>
      <span v-else-if="latestDate" class="sp-metric-card__date">
        {{ zhCN.p01.metricSource }} {{ latestDate }}
      </span>
      <span v-if="clickable !== false" class="sp-metric-card__hint">
        {{ zhCN.p01.metricHint }}
      </span>
    </span>
  </button>
</template>

<style scoped>
.sp-metric-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  width: 100%;
  min-width: 0;
  padding: 12px 14px 11px;
  text-align: left;
  background: var(--sp-surface);
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  transition: border-color 120ms ease, background-color 120ms ease;
}

.sp-metric-card:not(.is-static):hover {
  border-color: var(--sp-primary);
  background: #fbfdfd;
}

.sp-metric-card.is-static {
  cursor: default;
}

.sp-metric-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sp-metric-card__label {
  font-size: 12px;
  color: var(--sp-muted);
  line-height: 18px;
}

.sp-metric-card__code {
  font-family: var(--sp-font-mono);
  font-size: 10px;
  color: var(--sp-faint);
  padding: 0 4px;
  border: 1px solid var(--sp-border);
  border-radius: 2px;
  line-height: 15px;
  white-space: nowrap;
}

.sp-metric-card__value-row {
  display: flex;
  align-items: baseline;
  gap: 5px;
  min-height: 32px;
}

.sp-metric-card__value {
  font-family: var(--sp-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 23px;
  line-height: 1.2;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--sp-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sp-metric-card__value.is-null {
  font-family: var(--sp-font);
  font-size: 16px;
  font-weight: 500;
  color: var(--sp-muted);
  letter-spacing: 0;
}

.sp-metric-card__unit {
  font-size: 11.5px;
  color: var(--sp-muted);
}

.sp-metric-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 16px;
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-metric-card__reason {
  color: var(--sp-warning);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sp-metric-card__date {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sp-metric-card__hint {
  flex: none;
  color: var(--sp-primary);
  opacity: 0;
  transition: opacity 120ms ease;
}

.sp-metric-card:hover .sp-metric-card__hint,
.sp-metric-card:focus-visible .sp-metric-card__hint {
  opacity: 1;
}

.is-null .sp-metric-card__hint {
  opacity: 1;
}
</style>
