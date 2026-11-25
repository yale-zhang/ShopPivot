<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElButton } from 'element-plus'

import { ApiError, fetchMetricCard } from '../api/client'
import type { MetricCardPayload } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { prettyJson } from '../utils/format'
import { labelForStatus, toneForStatus } from '../utils/status'
import DrawerPanel from './DrawerPanel.vue'
import RunDetailDrawer from './RunDetailDrawer.vue'
import StateView from './StateView.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  open: boolean
  metricCode: string | null
  metricLabel?: string
  runId?: string | null
}>()

const emit = defineEmits<{ (event: 'update:open', value: boolean): void }>()

const metric = ref<MetricCardPayload | null>(null)
const loading = ref(false)
const errorText = ref('')
const runOpen = ref(false)
let seq = 0

const title = computed(() =>
  props.metricLabel ? `${zhCN.drill.title} · ${props.metricLabel}` : zhCN.drill.title,
)

const subtitle = computed(() => props.metricCode ?? '')

const additivityLabel = computed(() => {
  const value = metric.value?.compute.additivity ?? ''
  return zhCN.drill.additivityLabels[value] ?? value
})

const nullPolicyLabel = computed(() => {
  const value = metric.value?.compute.null_policy ?? ''
  return zhCN.drill.nullPolicyLabels[value] ?? value
})

const inspected = computed(() => metric.value?.evidence.last_inspected_value ?? null)

const inspectedIsNull = computed(() => {
  const value = inspected.value
  if (!value) return true
  return value.value === null || value.null_reason !== null
})

const resolvedRunId = computed(() => metric.value?.evidence.run_id || props.runId || null)

const readOnly = computed(() => Boolean(metric.value?.readonly))

async function load(): Promise<void> {
  if (!props.metricCode) return
  const current = ++seq
  loading.value = true
  errorText.value = ''
  try {
    const payload = await fetchMetricCard(props.metricCode)
    if (current !== seq) return
    metric.value = payload
  } catch (cause) {
    if (current !== seq) return
    errorText.value =
      cause instanceof ApiError
        ? cause.userMessage
        : cause && typeof cause === 'object' && 'userMessage' in cause
          ? String((cause as { userMessage: unknown }).userMessage)
          : zhCN.drill.loadFailed
  } finally {
    if (current === seq) loading.value = false
  }
}

function close(): void {
  runOpen.value = false
  emit('update:open', false)
}

function openRun(): void {
  if (resolvedRunId.value) runOpen.value = true
}

watch(
  () => [props.open, props.metricCode] as const,
  ([open]) => {
    if (open) void load()
    else {
      metric.value = null
      runOpen.value = false
    }
  },
  { immediate: true },
)
</script>

<template>
  <DrawerPanel
    :open="open"
    :title="title"
    :subtitle="subtitle"
    width="580px"
    :z-index="1000"
    :close-label="zhCN.drill.close"
    @close="close"
  >
    <StateView v-if="loading" state="loading" compact />
    <StateView
      v-else-if="errorText"
      state="error"
      :title="zhCN.drill.loadFailed"
      :description="errorText"
      compact
      @retry="load"
    />
    <div v-else-if="metric" class="sp-drill">
      <div class="sp-drill__head">
        <StatusBadge :label="labelForStatus(metric.status)" :tone="toneForStatus(metric.status)" dot />
        <span class="sp-chip sp-chip--primary">{{ metric.metric_code }}</span>
        <span class="sp-chip">{{ zhCN.drill.version }} · {{ metric.version }}</span>
        <span v-if="readOnly" class="sp-chip">{{ zhCN.common.readonlyMode }}</span>
      </div>

      <section class="sp-drill__section">
        <h3 class="sp-section-label">{{ zhCN.drill.definition }}</h3>
        <div class="sp-drill__name">{{ metric.display_name }}</div>
        <p class="sp-drill__question">{{ metric.business_question }}</p>
        <div v-if="metric.synonyms.length" class="sp-drill__chips">
          <span v-for="synonym in metric.synonyms" :key="synonym" class="sp-chip">{{ synonym }}</span>
        </div>
        <div class="sp-drill__concept">
          <span class="sp-faint">{{ zhCN.drill.concept }}</span>
          <span class="sp-mono-break">{{ metric.concept_uri }}</span>
        </div>
      </section>

      <section class="sp-drill__section">
        <h3 class="sp-section-label">{{ zhCN.drill.calculation }}</h3>
        <div class="sp-drill__formula">
          <span class="sp-faint">{{ zhCN.drill.formula }}</span>
          <code>{{ metric.compute.formula }}</code>
        </div>
        <dl class="sp-drill__grid">
          <dt>{{ zhCN.drill.denominator }}</dt>
          <dd class="sp-mono">{{ metric.compute.denominator || zhCN.common.none }}</dd>
          <dt>{{ zhCN.drill.unit }}</dt>
          <dd>{{ metric.compute.unit }}</dd>
          <dt>{{ zhCN.drill.precision }}</dt>
          <dd class="sp-mono">{{ metric.compute.precision }}</dd>
          <dt>{{ zhCN.drill.additivity }}</dt>
          <dd>
            <span :class="{ 'sp-drill__warn': metric.compute.additivity !== 'ADDITIVE' }">
              {{ additivityLabel }}
            </span>
          </dd>
          <dt>{{ zhCN.drill.nullPolicy }}</dt>
          <dd>{{ nullPolicyLabel }}</dd>
          <dt>{{ zhCN.drill.sourceMapping }}</dt>
          <dd class="sp-mono-break">{{ metric.compute.source_mapping }}</dd>
          <dt>{{ zhCN.drill.effectiveFrom }}</dt>
          <dd class="sp-mono">{{ metric.effective_from }}</dd>
          <dt>{{ zhCN.drill.breakingChange }}</dt>
          <dd>{{ metric.breaking_change ? zhCN.common.yes : zhCN.common.no }}</dd>
        </dl>
      </section>

      <section class="sp-drill__section">
        <h3 class="sp-section-label">{{ zhCN.drill.probeSql }}</h3>
        <pre class="sp-drill__code">{{ metric.evidence.probe_sql_template }}</pre>
      </section>

      <section class="sp-drill__section">
        <h3 class="sp-section-label">{{ zhCN.drill.inspectedValue }}</h3>
        <div v-if="inspected" class="sp-drill__inspected">
          <span class="sp-drill__value" :class="{ 'is-null': inspectedIsNull }">
            {{ inspectedIsNull ? zhCN.common.notAvailable : inspected.value }}
          </span>
          <span class="sp-faint">{{ zhCN.drill.inspectedDate }} {{ inspected.stat_date }}</span>
          <span v-if="inspected.null_reason" class="sp-drill__warn">
            {{ zhCN.p01.nullReason(inspected.null_reason) }}
          </span>
        </div>
        <p v-else class="sp-faint">{{ zhCN.drill.inspectedEmpty }}</p>
      </section>

      <section class="sp-drill__section">
        <div class="sp-drill__section-head">
          <h3 class="sp-section-label">{{ zhCN.drill.qualityTests }}</h3>
          <StatusBadge
            :label="
              metric.quality.release_gate_passed
                ? zhCN.drill.releaseGatePassed
                : zhCN.drill.releaseGateFailed
            "
            :tone="metric.quality.release_gate_passed ? 'success' : 'danger'"
          />
        </div>
        <ul v-if="metric.quality.quality_tests.length" class="sp-drill__tests">
          <li v-for="test in metric.quality.quality_tests" :key="test" class="sp-drill__test">
            <span class="sp-drill__test-mark" aria-hidden="true">·</span>
            {{ test }}
          </li>
        </ul>
        <p v-else class="sp-faint">{{ zhCN.common.none }}</p>
      </section>

      <section class="sp-drill__section">
        <h3 class="sp-section-label">{{ zhCN.drill.odsRefs }}</h3>
        <div v-if="metric.evidence.ods_refs.length" class="sp-drill__refs">
          <span
            v-for="ref in metric.evidence.ods_refs"
            :key="ref"
            class="sp-chip sp-mono-break"
            :title="ref"
          >
            {{ ref }}
          </span>
        </div>
        <p v-else class="sp-faint">{{ zhCN.drill.odsEmpty }}</p>
      </section>

      <section class="sp-drill__run">
        <div class="sp-drill__run-id">
          <span class="sp-section-label">{{ zhCN.drill.runLink }}</span>
          <span class="sp-mono-break">{{ resolvedRunId || zhCN.drill.noRun }}</span>
        </div>
        <ElButton v-if="resolvedRunId" size="small" @click="openRun">
          {{ zhCN.drill.runLink }}
        </ElButton>
      </section>

      <details v-if="metric.card" class="sp-drill__raw">
        <summary>{{ zhCN.drill.cardJson }}</summary>
        <pre class="sp-drill__code">{{ prettyJson(metric.card) }}</pre>
      </details>
    </div>

    <RunDetailDrawer v-model:open="runOpen" :run-id="resolvedRunId" />
  </DrawerPanel>
</template>

<style scoped>
.sp-drill {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sp-drill__head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.sp-drill__section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sp-drill__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sp-drill__name {
  font-size: 15px;
  font-weight: 650;
  color: var(--sp-text);
}

.sp-drill__question {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--sp-muted);
}

.sp-drill__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.sp-drill__concept {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-drill__formula {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border: 1px solid var(--sp-primary-soft-strong);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-primary-soft);
}

.sp-drill__formula code {
  font-size: 12.5px;
  color: var(--sp-primary);
  word-break: break-word;
}

.sp-drill__grid {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr) 72px minmax(0, 1fr);
  gap: 4px 10px;
  margin: 0;
  padding: 9px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 11.5px;
}

.sp-drill__grid dt {
  color: var(--sp-muted);
}

.sp-drill__grid dd {
  margin: 0;
  min-width: 0;
  color: var(--sp-text);
  word-break: break-word;
}

.sp-drill__warn {
  color: var(--sp-warning);
  font-weight: 500;
}

.sp-drill__code {
  margin: 0;
  padding: 9px 10px;
  max-height: 260px;
  overflow: auto;
  background: var(--sp-surface-sunken);
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  font-size: 11px;
  line-height: 1.55;
  color: var(--sp-text);
  white-space: pre-wrap;
  word-break: break-word;
}

.sp-drill__inspected {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
}

.sp-drill__value {
  font-family: var(--sp-font-mono);
  font-size: 18px;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-drill__value.is-null {
  font-family: var(--sp-font);
  font-size: 13px;
  color: var(--sp-muted);
}

.sp-drill__tests {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sp-drill__test {
  font-size: 11.5px;
  color: var(--sp-text);
}

.sp-drill__test-mark {
  color: var(--sp-primary);
  margin-right: 4px;
}

.sp-drill__refs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.sp-drill__run {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface);
}

.sp-drill__run-id {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-drill__raw summary {
  cursor: pointer;
  font-size: 11.5px;
  color: var(--sp-muted);
}

.sp-drill__raw[open] summary {
  margin-bottom: 5px;
}

@media (max-width: 560px) {
  .sp-drill__grid {
    grid-template-columns: 92px minmax(0, 1fr);
  }
}
</style>
