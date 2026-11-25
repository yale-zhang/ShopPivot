<script setup lang="ts">
import { ref, watch } from 'vue'

import { ApiError, fetchEvidence } from '../api/client'
import type { EvidencePayload } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { formatDateTime, prettyJson } from '../utils/format'
import DrawerPanel from './DrawerPanel.vue'
import StateView from './StateView.vue'

const props = defineProps<{
  open: boolean
  runId: string | null
  payloadId: number | null
}>()

const emit = defineEmits<{ (event: 'close'): void }>()

const evidence = ref<EvidencePayload | null>(null)
const loading = ref(false)
const errorText = ref('')
let requestSeq = 0

async function load(): Promise<void> {
  if (!props.runId || props.payloadId === null) return
  const seq = ++requestSeq
  loading.value = true
  errorText.value = ''
  try {
    const payload = await fetchEvidence(props.runId, props.payloadId)
    if (seq !== requestSeq) return
    evidence.value = payload
  } catch (cause) {
    if (seq !== requestSeq) return
    errorText.value =
      cause instanceof ApiError
        ? cause.userMessage
        : cause && typeof cause === 'object' && 'userMessage' in cause
          ? String((cause as { userMessage: unknown }).userMessage)
          : zhCN.run.evidenceLoadFailed
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

watch(
  () => [props.open, props.runId, props.payloadId] as const,
  ([open]) => {
    if (open) void load()
    else evidence.value = null
  },
  { immediate: true },
)
</script>

<template>
  <DrawerPanel
    :open="open"
    :title="zhCN.run.evidenceTitle"
    :subtitle="payloadId !== null ? `${zhCN.run.payloadHash} · ${payloadId}` : ''"
    width="600px"
    :z-index="1200"
    :close-label="zhCN.run.closeEvidence"
    @close="emit('close')"
  >
    <StateView v-if="loading" state="loading" compact />
    <StateView
      v-else-if="errorText"
      state="error"
      :title="zhCN.run.evidenceLoadFailed"
      :description="errorText"
      compact
      @retry="load"
    />
    <div v-else-if="evidence" class="sp-evidence-detail">
      <div class="sp-evidence-detail__masked" role="note">
        {{ evidence.masked_copy || zhCN.evidence.masked }}
      </div>
      <div class="sp-evidence-detail__meta">
        <span class="sp-chip">{{ evidence.dataset }}</span>
        <span class="sp-chip">{{ evidence.channel }}</span>
        <span class="sp-chip">{{ evidence.record_count }} {{ zhCN.run.recordsUnit }}</span>
        <span class="sp-chip">{{ formatDateTime(evidence.fetched_at) }}</span>
        <span v-if="evidence.masked" class="sp-chip sp-chip--primary">{{ zhCN.run.evidenceMasked }}</span>
      </div>
      <div class="sp-evidence-detail__hash">
        <span class="sp-section-label">{{ zhCN.run.payloadHash }}</span>
        <span class="sp-mono-break">{{ evidence.payload_hash }}</span>
      </div>
      <div>
        <div class="sp-section-label">{{ zhCN.run.evidenceJson }}</div>
        <pre class="sp-evidence-detail__json">{{ prettyJson(evidence.payload) }}</pre>
      </div>
    </div>
  </DrawerPanel>
</template>

<style scoped>
.sp-evidence-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sp-evidence-detail__masked {
  padding: 7px 10px;
  border: 1px solid var(--sp-warning-border);
  border-left: 3px solid var(--sp-warning);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-warning-soft);
  color: #6d4a12;
  font-size: 11.5px;
}

.sp-evidence-detail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.sp-evidence-detail__hash {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-evidence-detail__json {
  margin: 4px 0 0;
  padding: 10px;
  max-height: 54vh;
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
</style>
