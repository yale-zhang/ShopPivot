<script setup lang="ts">
import { computed } from 'vue'

import { zhCN } from '../i18n/zh-CN'
import { prettyJson } from '../utils/format'

const props = defineProps<{
  plan: unknown
  impactScope?: string | null
}>()

const hasPlan = computed(() => {
  if (props.plan === null || props.plan === undefined) return false
  if (typeof props.plan === 'string') return props.plan.trim().length > 0
  if (Array.isArray(props.plan)) return props.plan.length > 0
  if (typeof props.plan === 'object') return Object.keys(props.plan as object).length > 0
  return true
})

const planText = computed(() => {
  if (!hasPlan.value) return ''
  return typeof props.plan === 'string' ? props.plan : prettyJson(props.plan)
})
</script>

<template>
  <div class="sp-rollback">
    <div class="sp-rollback__block">
      <div class="sp-section-label">{{ zhCN.p06.rollback.plan }}</div>
      <p v-if="hasPlan" class="sp-rollback__plan">{{ planText }}</p>
      <p v-else class="sp-rollback__plan is-empty">{{ zhCN.p06.rollback.empty }}</p>
    </div>

    <div v-if="impactScope" class="sp-rollback__block">
      <div class="sp-section-label">{{ zhCN.p06.rollback.impact }}</div>
      <p class="sp-rollback__impact">{{ impactScope }}</p>
    </div>

    <div class="sp-rollback__risk">
      <div class="sp-section-label">{{ zhCN.p06.rollback.risk }}</div>
      <p>{{ zhCN.p06.rollback.note }}</p>
    </div>
  </div>
</template>

<style scoped>
.sp-rollback {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sp-rollback__block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sp-rollback__plan,
.sp-rollback__impact {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--sp-text);
  white-space: pre-wrap;
  word-break: break-word;
}

.sp-rollback__plan {
  padding: 8px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-family: var(--sp-font-mono);
  font-size: 11.5px;
}

.sp-rollback__plan.is-empty {
  color: var(--sp-danger);
  font-family: var(--sp-font);
  background: var(--sp-danger-soft);
  border-color: var(--sp-danger-border);
}

.sp-rollback__risk {
  padding: 8px 10px;
  border: 1px solid var(--sp-warning-border);
  border-left: 3px solid var(--sp-warning);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-warning-soft);
}

.sp-rollback__risk p {
  margin-top: 2px;
  font-size: 11.5px;
  line-height: 1.55;
  color: #6d4a12;
}
</style>
