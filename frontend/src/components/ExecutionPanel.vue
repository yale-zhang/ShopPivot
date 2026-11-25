<script setup lang="ts">
import { computed } from 'vue'

import type { ChangeOrderExecution } from '../api/types'
import { zhCN, type Tone } from '../i18n/zh-CN'
import { formatDateTime, prettyJson } from '../utils/format'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  execution: ChangeOrderExecution
  planStatus: string | null
}>()

const EXECUTION_TONES: Record<string, Tone> = {
  VERIFIED: 'success',
  FAILED: 'danger',
  RUNNING: 'warning',
}

const tone = computed<Tone>(() => EXECUTION_TONES[props.execution.status] ?? 'neutral')

const statusLabel = computed(
  () =>
    zhCN.p06.execution.statusLabels[props.execution.status] ??
    props.execution.status,
)

const verifyText = computed(() => {
  const value = props.execution.verify_result
  if (value === null || value === undefined) return ''
  try {
    const serialized = JSON.stringify(value)
    if (!serialized || serialized === '{}' || serialized === 'null') return ''
  } catch {
    return ''
  }
  return prettyJson(value)
})

const endedAt = computed(() => formatDateTime(props.execution.ended_at))
const compensated = computed(() => props.planStatus === 'COMPENSATED')
</script>

<template>
  <div class="sp-execution" :class="`sp-execution--${tone}`" :data-execution-status="execution.status">
    <div class="sp-execution__banner" :class="`sp-execution__banner--${tone}`">
      <StatusBadge :label="statusLabel" :tone="tone" dot />
      <span class="sp-execution__id sp-mono">{{ execution.execution_id }}</span>
    </div>

    <div v-if="execution.status === 'FAILED'" class="sp-execution__notice sp-execution__notice--danger" role="alert">
      {{ zhCN.p06.execution.failedNotice }}
    </div>
    <div v-else-if="execution.status === 'RUNNING'" class="sp-execution__notice sp-execution__notice--warning">
      {{ zhCN.p06.execution.runningNotice }}
    </div>
    <div v-if="compensated" class="sp-execution__notice sp-execution__notice--warning" data-role="compensated">
      {{ zhCN.p06.execution.compensatedNotice }}
    </div>

    <dl class="sp-execution__grid">
      <dt>{{ zhCN.p06.execution.beforeShot }}</dt>
      <dd class="sp-mono-break">{{ execution.before_shot || zhCN.common.none }}</dd>
      <dt>{{ zhCN.p06.execution.afterShot }}</dt>
      <dd class="sp-mono-break">{{ execution.after_shot || zhCN.common.none }}</dd>
      <dt>{{ zhCN.p06.execution.verifyResult }}</dt>
      <dd>
        <pre v-if="verifyText" class="sp-execution__verify">{{ verifyText }}</pre>
        <span v-else>{{ zhCN.common.none }}</span>
      </dd>
      <dt>{{ zhCN.p06.execution.errCode }}</dt>
      <dd class="sp-mono">{{ execution.err_code || zhCN.common.none }}</dd>
      <dt>{{ zhCN.p06.execution.errLayer }}</dt>
      <dd class="sp-mono">{{ execution.err_layer || zhCN.common.none }}</dd>
      <dt>{{ zhCN.p06.execution.endedAt }}</dt>
      <dd>{{ endedAt || zhCN.common.none }}</dd>
    </dl>
  </div>
</template>

<style scoped>
.sp-execution {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.sp-execution__banner {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
}

.sp-execution__banner--success {
  border-color: var(--sp-success-border);
  background: var(--sp-success-soft);
}

.sp-execution__banner--danger {
  border-color: var(--sp-danger-border);
  background: var(--sp-danger-soft);
}

.sp-execution__banner--warning {
  border-color: var(--sp-warning-border);
  background: var(--sp-warning-soft);
}

.sp-execution__id {
  font-size: 10.5px;
  color: var(--sp-muted);
  word-break: break-all;
}

.sp-execution__notice {
  padding: 7px 10px;
  border: 1px solid var(--sp-border);
  border-left-width: 3px;
  border-radius: var(--sp-radius-sm);
  font-size: 12px;
  font-weight: 500;
}

.sp-execution__notice--danger {
  border-color: var(--sp-danger-border);
  border-left-color: var(--sp-danger);
  background: var(--sp-danger-soft);
  color: var(--sp-danger);
}

.sp-execution__notice--warning {
  border-color: var(--sp-warning-border);
  border-left-color: var(--sp-warning);
  background: var(--sp-warning-soft);
  color: #6d4a12;
}

.sp-execution__grid {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 4px 10px;
  margin: 0;
  padding: 9px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 11.5px;
}

.sp-execution__grid dt {
  color: var(--sp-muted);
}

.sp-execution__grid dd {
  margin: 0;
  min-width: 0;
  color: var(--sp-text);
  word-break: break-word;
}

.sp-execution__verify {
  max-height: 180px;
  margin: 0;
  overflow: auto;
  font-family: var(--sp-font-mono);
  font-size: 10.5px;
  color: var(--sp-text);
  white-space: pre-wrap;
}
</style>
