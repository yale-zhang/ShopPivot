<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElButton } from 'element-plus'

import { ApiError, fetchRun } from '../api/client'
import type { RunDetailPayload } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { formatDate, formatDateTime, truncateMiddle } from '../utils/format'
import { labelForStatus, toneForStatus } from '../utils/status'
import DrawerPanel from './DrawerPanel.vue'
import EvidenceDrawer from './EvidenceDrawer.vue'
import StateView from './StateView.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  open: boolean
  runId: string | null
}>()

const emit = defineEmits<{ (event: 'update:open', value: boolean): void }>()

const detail = ref<RunDetailPayload | null>(null)
const loading = ref(false)
const errorText = ref('')
const evidenceOpen = ref(false)
const evidencePayloadId = ref<number | null>(null)
let requestSeq = 0

const subtitle = computed(() => props.runId ?? '')

const windowText = computed(() => {
  if (!detail.value) return ''
  return `${formatDate(detail.value.window.start)} ~ ${formatDate(detail.value.window.end)}`
})

async function load(): Promise<void> {
  if (!props.runId) return
  const seq = ++requestSeq
  loading.value = true
  errorText.value = ''
  try {
    const payload = await fetchRun(props.runId)
    if (seq !== requestSeq) return
    detail.value = payload
  } catch (cause) {
    if (seq !== requestSeq) return
    errorText.value =
      cause instanceof ApiError
        ? cause.userMessage
        : cause && typeof cause === 'object' && 'userMessage' in cause
          ? String((cause as { userMessage: unknown }).userMessage)
          : zhCN.run.loadFailed
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function close(): void {
  emit('update:open', false)
}

function openEvidence(payloadId: number): void {
  evidencePayloadId.value = payloadId
  evidenceOpen.value = true
}

watch(
  () => [props.open, props.runId] as const,
  ([open]) => {
    if (open) void load()
    else {
      detail.value = null
      evidenceOpen.value = false
      evidencePayloadId.value = null
    }
  },
  { immediate: true },
)
</script>

<template>
  <DrawerPanel
    :open="open"
    :title="zhCN.run.title"
    :subtitle="subtitle"
    width="700px"
    :z-index="1100"
    :close-label="zhCN.run.close"
    @close="close"
  >
    <StateView v-if="loading" state="loading" compact />
    <StateView
      v-else-if="errorText"
      state="error"
      :title="zhCN.run.loadFailed"
      :description="errorText"
      compact
      @retry="load"
    />
    <div v-else-if="detail" class="sp-run">
      <div class="sp-run__head">
        <StatusBadge :label="labelForStatus(detail.status)" :tone="toneForStatus(detail.status)" dot />
        <span class="sp-chip">{{ zhCN.run.gate }} · {{ detail.gate_level_max }}</span>
        <span class="sp-chip sp-mono">{{ detail.run_id }}</span>
      </div>

      <section class="sp-run__summary">
        <div class="sp-kv__key">{{ zhCN.run.scene }}</div>
        <div class="sp-kv__value sp-mono">{{ detail.scene }}</div>
        <div class="sp-kv__key">{{ zhCN.run.platform }}</div>
        <div class="sp-kv__value">{{ detail.platform }} / {{ detail.shop_id }}</div>
        <div class="sp-kv__key">{{ zhCN.run.window }}</div>
        <div class="sp-kv__value">{{ windowText }}</div>
        <div class="sp-kv__key">{{ zhCN.run.startedAt }}</div>
        <div class="sp-kv__value">{{ formatDateTime(detail.started_at) || zhCN.common.none }}</div>
        <div class="sp-kv__key">{{ zhCN.run.endedAt }}</div>
        <div class="sp-kv__value">{{ formatDateTime(detail.ended_at) || zhCN.common.none }}</div>
        <div class="sp-kv__key">{{ zhCN.run.configHash }}</div>
        <div class="sp-kv__value sp-mono-break" :title="detail.config_snapshot_hash">
          {{ truncateMiddle(detail.config_snapshot_hash, 18, 6) }}
        </div>
      </section>

      <section class="sp-run__section">
        <h3 class="sp-section-label">{{ zhCN.run.nodes }}</h3>
        <div v-if="detail.nodes.length" class="sp-run__table-wrap">
          <table class="sp-run__table">
            <thead>
              <tr>
                <th scope="col">{{ zhCN.run.nodeId }}</th>
                <th scope="col">{{ zhCN.run.status }}</th>
                <th scope="col">{{ zhCN.run.cost }}</th>
                <th scope="col">{{ zhCN.run.channel }}</th>
                <th scope="col">{{ zhCN.run.payloadDigest }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="node in detail.nodes" :key="node.node_id">
                <td class="sp-mono sp-run__node-id">{{ node.node_id }}</td>
                <td>
                  <StatusBadge :label="labelForStatus(node.status)" :tone="toneForStatus(node.status)" />
                </td>
                <td class="sp-mono">
                  {{ node.cost_ms === null ? zhCN.common.none : `${node.cost_ms} ${zhCN.run.costUnit}` }}
                </td>
                <td class="sp-mono">{{ node.channel || zhCN.common.none }}</td>
                <td class="sp-mono sp-run__digest" :title="node.payload_digest || ''">
                  {{ node.payload_digest ? truncateMiddle(node.payload_digest, 10, 4) : zhCN.common.none }}
                  <span v-if="node.err_code" class="sp-run__err">{{ node.err_code }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="sp-run__empty">{{ zhCN.run.nodeEmpty }}</p>
      </section>

      <section class="sp-run__section">
        <h3 class="sp-section-label">{{ zhCN.run.ods }}</h3>
        <div v-if="detail.ods.length" class="sp-run__ods">
          <div v-for="item in detail.ods" :key="item.id" class="sp-run__ods-row">
            <div class="sp-run__ods-main">
              <div class="sp-run__ods-head">
                <span class="sp-chip sp-chip--primary">{{ item.dataset }}</span>
                <span class="sp-chip">{{ item.channel }}</span>
                <span class="sp-chip">{{ item.record_count }} {{ zhCN.run.recordsUnit }}</span>
                <span class="sp-faint">{{ formatDateTime(item.fetched_at) }}</span>
              </div>
              <div class="sp-run__ods-hash sp-mono-break" :title="item.payload_hash">
                {{ truncateMiddle(item.payload_hash, 22, 8) }}
              </div>
            </div>
            <ElButton size="small" @click="openEvidence(item.id)">
              {{ zhCN.run.viewEvidence }}
            </ElButton>
          </div>
        </div>
        <p v-else class="sp-run__empty">{{ zhCN.run.odsEmpty }}</p>
      </section>

      <section v-if="detail.reports.length" class="sp-run__section">
        <h3 class="sp-section-label">{{ zhCN.run.exportedReports }}</h3>
        <ul class="sp-run__reports">
          <li v-for="report in detail.reports" :key="report.report_id" class="sp-run__report">
            <span class="sp-mono">{{ report.report_id }}</span>
            <span class="sp-chip">{{ report.metric_version }}</span>
            <span class="sp-faint">{{ formatDateTime(report.generated_at) }}</span>
          </li>
        </ul>
      </section>
    </div>

    <EvidenceDrawer
      :open="evidenceOpen"
      :run-id="runId"
      :payload-id="evidencePayloadId"
      @close="evidenceOpen = false"
    />
  </DrawerPanel>
</template>

<style scoped>
.sp-run {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sp-run__head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.sp-run__summary {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr) 92px minmax(0, 1fr);
  gap: 4px 10px;
  padding: 10px 12px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 12px;
}

.sp-run__section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sp-run__table-wrap {
  overflow-x: auto;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
}

.sp-run__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

.sp-run__table th {
  padding: 5px 8px;
  background: var(--sp-surface-sunken);
  border-bottom: 1px solid var(--sp-border);
  font-size: 10px;
  font-weight: 600;
  color: var(--sp-muted);
  text-align: left;
  white-space: nowrap;
}

.sp-run__table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--sp-border);
  vertical-align: middle;
}

.sp-run__table tbody tr:last-child td {
  border-bottom: 0;
}

.sp-run__node-id {
  font-weight: 600;
  color: var(--sp-text);
}

.sp-run__digest {
  max-width: 190px;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-run__err {
  margin-left: 5px;
  color: var(--sp-danger);
}

.sp-run__empty {
  padding: 10px;
  border: 1px dashed var(--sp-border);
  border-radius: var(--sp-radius-sm);
  font-size: 11.5px;
  color: var(--sp-muted);
  text-align: center;
}

.sp-run__ods {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  overflow: hidden;
}

.sp-run__ods-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--sp-border);
}

.sp-run__ods-row:last-child {
  border-bottom: 0;
}

.sp-run__ods-main {
  min-width: 0;
}

.sp-run__ods-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 10.5px;
}

.sp-run__ods-hash {
  margin-top: 2px;
  font-size: 10px;
  color: var(--sp-muted);
}

.sp-run__reports {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.sp-run__report {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  font-size: 11.5px;
}

@media (max-width: 620px) {
  .sp-run__summary {
    grid-template-columns: 88px minmax(0, 1fr);
  }
}
</style>
