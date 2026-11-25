<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { zhCN } from '../i18n/zh-CN'
import { formatCountdown } from '../utils/format'

const props = defineProps<{
  remainingSeconds: number | null
  status: string
  overdue?: boolean
  syncedAt?: number
}>()

const mountedAt = Date.now()
const now = ref(Date.now())
let timer: number | null = null

const isPending = computed(() => props.status === 'PENDING')
const isExpired = computed(() => props.status === 'EXPIRED')

const effectiveRemaining = computed(() => {
  if (props.remainingSeconds === null || props.remainingSeconds === undefined) return null
  const baseline = props.syncedAt ?? mountedAt
  const elapsed = Math.max(0, Math.floor((now.value - baseline) / 1000))
  return props.remainingSeconds - Math.max(0, elapsed)
})

const isOverdue = computed(
  () => isPending.value && (Boolean(props.overdue) || (effectiveRemaining.value ?? 1) <= 0),
)

onMounted(() => {
  if (typeof window === 'undefined') return
  if (!isPending.value || props.remainingSeconds === null) return
  timer = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
})
</script>

<template>
  <span v-if="isExpired" class="sp-countdown sp-countdown--expired">
    {{ zhCN.components.countdown.expired }}
  </span>
  <span v-else-if="isOverdue" class="sp-countdown sp-countdown--overdue">
    {{ zhCN.components.countdown.overdue }}
  </span>
  <span v-else-if="isPending && effectiveRemaining !== null" class="sp-countdown">
    <span class="sp-countdown__label">{{ zhCN.components.countdown.remaining }}</span>
    <span class="sp-countdown__time">{{ formatCountdown(effectiveRemaining) }}</span>
  </span>
  <span v-else class="sp-countdown sp-countdown--na">
    {{ zhCN.components.countdown.notApplicable }}
  </span>
</template>

<style scoped>
.sp-countdown {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  font-size: 12px;
  color: var(--sp-text);
  white-space: nowrap;
}

.sp-countdown__label {
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-countdown__time {
  font-family: var(--sp-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 12.5px;
  font-weight: 600;
}

.sp-countdown--overdue {
  color: var(--sp-warning);
  font-weight: 600;
}

.sp-countdown--expired {
  color: var(--sp-readonly);
  font-size: 11px;
  line-height: 1.4;
  white-space: normal;
}

.sp-countdown--na {
  color: var(--sp-faint);
}
</style>
