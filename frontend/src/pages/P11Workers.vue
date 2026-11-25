<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElButton, ElTable, ElTableColumn } from 'element-plus'

import {
  ApiError,
  fetchExceptions,
  fetchWorkers,
  registerDemoWorker,
} from '../api/client'
import type { ExceptionRecord, ExceptionsResponse, WorkersResponse } from '../api/types'
import { zhCN, type Tone } from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useContextStore } from '../stores/context'
import { useShellStore } from '../stores/shell'
import { useToast } from '../composables/useToast'
import { formatDateTime } from '../utils/format'
import { labelForStatus, toneForStatus } from '../utils/status'
import KpiTile from '../components/KpiTile.vue'
import PageHeader from '../components/PageHeader.vue'
import RunDetailDrawer from '../components/RunDetailDrawer.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

interface LayerGroup {
  code: string
  label: string
  desc: string
  items: ExceptionRecord[]
}

const LAYER_CODES = ['UI', 'SYS', 'DATA', 'CODE'] as const

const session = useSessionStore()
const context = useContextStore()
const shell = useShellStore()
const { push } = useToast()

const workers = ref<WorkersResponse | null>(null)
const exceptions = ref<ExceptionsResponse | null>(null)
const workersLoading = ref(true)
const exceptionsLoading = ref(true)
const workersError = ref('')
const exceptionsError = ref('')
const registerPending = ref(false)
const runOpen = ref(false)
const activeRunId = ref<string | null>(null)

const role = computed(() => session.role || context.role)
const canRegister = computed(() => role.value === 'OWNER')
const workerItems = computed(() => workers.value?.items ?? [])
const exceptionItems = computed(() => exceptions.value?.items ?? [])
const workerEmptyCopy = computed(() => workers.value?.empty_copy || zhCN.p11.emptyWorkers)

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError) return cause.userMessage || fallback
  if (cause && typeof cause === 'object' && 'userMessage' in cause) {
    return String((cause as { userMessage: unknown }).userMessage) || fallback
  }
  return fallback
}

function layerMeta(code: string): { label: string; desc: string } {
  return zhCN.p11.layers[code] ?? { label: code, desc: '' }
}

const groups = computed<LayerGroup[]>(() => {
  const buckets = new Map<string, ExceptionRecord[]>()
  for (const code of LAYER_CODES) buckets.set(code, [])
  for (const item of exceptionItems.value) {
    const raw = (item.err_layer || '').toUpperCase()
    const code = (LAYER_CODES as readonly string[]).includes(raw) ? raw : 'OTHER'
    if (!buckets.has(code)) buckets.set(code, [])
    buckets.get(code)?.push(item)
  }
  return Array.from(buckets.entries()).map(([code, items]) => ({
    code,
    label: layerMeta(code).label,
    desc: layerMeta(code).desc,
    items,
  }))
})

const totalExceptions = computed(() => exceptionItems.value.length)

function kindLabel(kind: string): string {
  return zhCN.p11.kindLabels[kind] ?? kind
}

function retryableLabel(retryable: boolean): string {
  return retryable ? zhCN.p11.retryable : zhCN.p11.notRetryable
}

function retryableTone(retryable: boolean): Tone {
  return retryable ? 'warning' : 'neutral'
}

function openRun(runId: string | null): void {
  if (!runId) return
  activeRunId.value = runId
  runOpen.value = true
}

async function loadWorkers(): Promise<void> {
  workersLoading.value = true
  workersError.value = ''
  try {
    workers.value = await fetchWorkers()
  } catch (cause) {
    workersError.value = errorMessage(cause, zhCN.p11.loadFailed)
  } finally {
    workersLoading.value = false
  }
}

async function loadExceptions(): Promise<void> {
  exceptionsLoading.value = true
  exceptionsError.value = ''
  try {
    exceptions.value = await fetchExceptions(100)
  } catch (cause) {
    exceptionsError.value = errorMessage(cause, zhCN.p11.loadFailed)
  } finally {
    exceptionsLoading.value = false
  }
}

async function load(): Promise<void> {
  await Promise.allSettled([loadWorkers(), loadExceptions()])
}

async function register(): Promise<void> {
  if (!canRegister.value) return
  registerPending.value = true
  try {
    const result = await registerDemoWorker()
    push(zhCN.p11.registerSuccess(result.worker_id), 'success')
    await loadWorkers()
    void shell.refreshStatus()
  } catch (cause) {
    push(errorMessage(cause, zhCN.p11.registerFailed), 'danger')
  } finally {
    registerPending.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="sp-page sp-p11">
    <PageHeader
      :eyebrow="zhCN.p11.eyebrow"
      :title="zhCN.p11.title"
      :description="zhCN.p11.description"
    >
      <template #meta>
        <StatusBadge v-if="!canRegister" :label="zhCN.p11.registerHint" tone="neutral" />
      </template>
      <template #actions>
        <ElButton
          v-if="canRegister"
          size="small"
          type="primary"
          :loading="registerPending"
          @click="register"
        >
          {{ zhCN.p11.register }}
        </ElButton>
        <ElButton size="small" :loading="workersLoading || exceptionsLoading" @click="load">
          {{ zhCN.p11.refresh }}
        </ElButton>
      </template>
    </PageHeader>

    <div class="sp-p11__note" role="note">{{ zhCN.p11.note }}</div>

    <section class="sp-p11__fleet">
      <KpiTile
        :label="zhCN.p11.online"
        :value="workers?.online ?? zhCN.common.none"
        :unit="zhCN.p11.onlineUnit"
        code="ONLINE"
        tone="success"
        :hint="zhCN.p11.fleetHint"
      />
    </section>

    <section class="sp-panel sp-p11__workers">
      <div class="sp-panel__header">
        <div class="sp-panel__title">
          <span>{{ zhCN.p11.fleetTitle }}</span>
          <span v-if="workerItems.length" class="sp-panel__count">{{ workerItems.length }}</span>
        </div>
        <span class="sp-panel__hint">{{ zhCN.p11.fleetHint }}</span>
      </div>
      <StateView v-if="workersLoading" state="loading" compact />
      <StateView
        v-else-if="workersError"
        state="error"
        :title="zhCN.p11.loadFailed"
        :description="workersError"
        compact
        @retry="loadWorkers"
      />
      <StateView
        v-else-if="!workerItems.length"
        state="empty"
        :title="workerEmptyCopy"
        :description="zhCN.p11.emptyWorkersHint"
        compact
      />
      <ElTable v-else :data="workerItems" size="small" border style="width: 100%">
        <ElTableColumn :label="zhCN.p11.workerColumns.id" min-width="150">
          <template #default="{ row }">
            <span class="sp-mono">{{ row.worker_id }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p11.workerColumns.kind" width="84">
          <template #default="{ row }">{{ kindLabel(row.kind) }}</template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p11.workerColumns.status" width="82">
          <template #default="{ row }">
            <StatusBadge :label="labelForStatus(row.status)" :tone="toneForStatus(row.status)" />
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p11.workerColumns.capabilities" min-width="220">
          <template #default="{ row }">
            <div v-if="row.capabilities.length" class="sp-p11__caps">
              <span v-for="cap in row.capabilities" :key="cap" class="sp-chip sp-mono">{{ cap }}</span>
            </div>
            <span v-else class="sp-faint">{{ zhCN.common.none }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p11.workerColumns.queue" width="92" align="right">
          <template #default="{ row }">
            <span class="sp-mono">{{ row.queue_depth }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p11.workerColumns.heartbeat" width="150">
          <template #default="{ row }">
            <span class="sp-p11__heartbeat sp-mono">
              {{ formatDateTime(row.last_heartbeat_at) || zhCN.common.none }}
            </span>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>

    <section class="sp-panel sp-p11__exceptions">
      <div class="sp-panel__header">
        <div class="sp-panel__title">
          <span>{{ zhCN.p11.exceptionTitle }}</span>
          <span v-if="totalExceptions" class="sp-panel__count">{{ totalExceptions }}</span>
        </div>
        <span class="sp-panel__hint">{{ zhCN.p11.exceptionHint }}</span>
      </div>

      <StateView v-if="exceptionsLoading" state="loading" compact />
      <StateView
        v-else-if="exceptionsError"
        state="error"
        :title="zhCN.p11.loadFailed"
        :description="exceptionsError"
        compact
        @retry="loadExceptions"
      />
      <template v-else>
        <div class="sp-p11__layers">
          <section
            v-for="group in groups"
            :key="group.code"
            class="sp-layer"
            :class="`sp-layer--${group.code}`"
          >
            <header class="sp-layer__head">
              <span class="sp-layer__code sp-mono">{{ group.label }}</span>
              <span class="sp-layer__desc">{{ group.desc }}</span>
              <span class="sp-layer__count sp-mono">{{ zhCN.p11.layerCount(group.items.length) }}</span>
            </header>
            <ul v-if="group.items.length" class="sp-layer__list">
              <li v-for="item in group.items" :key="item.id" class="sp-exception">
                <div class="sp-exception__head">
                  <span class="sp-chip sp-exception__code sp-mono">{{ item.err_code }}</span>
                  <span class="sp-exception__message">{{ item.message }}</span>
                  <StatusBadge
                    :label="retryableLabel(item.retryable)"
                    :tone="retryableTone(item.retryable)"
                  />
                </div>
                <div class="sp-exception__meta">
                  <span class="sp-exception__meta-item">
                    <span class="sp-faint">{{ zhCN.p11.meta.runId }}</span>
                    <button
                      v-if="item.run_id"
                      type="button"
                      class="sp-link-btn sp-mono"
                      :title="zhCN.p11.viewRun"
                      @click="openRun(item.run_id)"
                    >
                      {{ item.run_id }}
                    </button>
                    <span v-else class="sp-mono">{{ zhCN.common.none }}</span>
                  </span>
                  <span class="sp-exception__meta-item">
                    <span class="sp-faint">{{ zhCN.p11.meta.nodeId }}</span>
                    <span class="sp-mono">{{ item.node_id || zhCN.common.none }}</span>
                  </span>
                  <span class="sp-exception__meta-item">
                    <span class="sp-faint">{{ zhCN.p11.meta.time }}</span>
                    <span>{{ formatDateTime(item.created_at) || zhCN.common.none }}</span>
                  </span>
                </div>
              </li>
            </ul>
            <p v-else class="sp-layer__empty">{{ zhCN.common.none }}</p>
          </section>
        </div>

        <StateView
          v-if="!totalExceptions"
          state="empty"
          :title="zhCN.p11.exceptionEmpty"
          :description="zhCN.p11.exceptionEmptyHint"
          compact
        />
      </template>
    </section>

    <RunDetailDrawer v-model:open="runOpen" :run-id="activeRunId" />
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p11__note {
  padding: 6px 11px;
  border: 1px solid var(--sp-info-border);
  border-left: 3px solid var(--sp-info);
  border-radius: var(--sp-radius);
  background: var(--sp-info-soft);
  color: var(--sp-info);
  font-size: 11.5px;
}

.sp-p11__fleet {
  max-width: 260px;
}

.sp-p11__caps {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.sp-p11__heartbeat {
  font-size: 10.5px;
  color: var(--sp-muted);
  white-space: nowrap;
}

.sp-p11__layers {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
}

.sp-layer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid var(--sp-border);
  border-top: 3px solid var(--sp-readonly);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
}

.sp-layer--UI {
  border-top-color: var(--sp-info);
}
.sp-layer--SYS {
  border-top-color: var(--sp-warning);
}
.sp-layer--DATA {
  border-top-color: var(--sp-primary);
}
.sp-layer--CODE {
  border-top-color: var(--sp-danger);
}
.sp-layer--OTHER {
  border-top-color: var(--sp-readonly);
}

.sp-layer__head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 5px 8px;
}

.sp-layer__code {
  font-size: 12px;
  font-weight: 700;
  color: var(--sp-text);
}

.sp-layer__desc {
  flex: 1;
  min-width: 0;
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-layer__count {
  font-size: 10px;
  color: var(--sp-muted);
}

.sp-layer__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sp-exception {
  padding: 7px 8px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
}

.sp-exception__head {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 6px;
}

.sp-exception__code {
  flex: none;
}

.sp-exception__message {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--sp-text);
  word-break: break-word;
}

.sp-exception__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 3px 12px;
  margin-top: 4px;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-exception__meta-item {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  min-width: 0;
}

.sp-layer__empty {
  font-size: 11px;
  color: var(--sp-faint);
}

@media (max-width: 1080px) {
  .sp-p11__layers {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
