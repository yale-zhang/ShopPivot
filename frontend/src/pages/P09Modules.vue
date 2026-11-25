<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElButton } from 'element-plus'

import { ApiError, disableModule, fetchModules } from '../api/client'
import type { ModuleInfo, ModulesResponse } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useShellStore } from '../stores/shell'
import { useToast } from '../composables/useToast'
import BlockingAlert from '../components/BlockingAlert.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ModuleList from '../components/ModuleList.vue'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

const session = useSessionStore()
const shell = useShellStore()
const { push } = useToast()

const payload = ref<ModulesResponse | null>(null)
const loading = ref(true)
const errorText = ref('')
const forbidden = ref(false)
const notice = ref('')
const confirmOpen = ref(false)
const pendingName = ref('')
const selected = ref<ModuleInfo | null>(null)

const canDisable = computed(() => session.isOwner || session.role === 'OWNER')
const readonly = computed(() => Boolean(payload.value?.readonly))

async function load(): Promise<void> {
  loading.value = true
  errorText.value = ''
  forbidden.value = false
  try {
    payload.value = await fetchModules()
  } catch (cause) {
    if (cause instanceof ApiError && (cause.status === 403 || cause.code === 'E003')) {
      forbidden.value = true
      return
    }
    errorText.value =
      cause instanceof ApiError
        ? cause.userMessage
        : cause && typeof cause === 'object' && 'userMessage' in cause
          ? String((cause as { userMessage: unknown }).userMessage)
          : zhCN.p09.loadFailed
  } finally {
    loading.value = false
  }
}

function askDisable(module: ModuleInfo): void {
  selected.value = module
  confirmOpen.value = true
  notice.value = ''
}

function cancelDisable(): void {
  if (pendingName.value) return
  confirmOpen.value = false
  selected.value = null
}

async function confirmDisable(): Promise<void> {
  const module = selected.value
  if (!module) return
  pendingName.value = module.name
  try {
    await disableModule(module.name)
    notice.value = zhCN.p09.disableSuccess(module.name)
    push(zhCN.p09.disableSuccess(module.name), 'success')
    confirmOpen.value = false
    selected.value = null
    await load()
    await Promise.all([shell.loadNav(), shell.refreshStatus()])
  } catch (cause) {
    const message =
      cause instanceof ApiError
        ? cause.userMessage
        : cause && typeof cause === 'object' && 'userMessage' in cause
          ? String((cause as { userMessage: unknown }).userMessage)
          : zhCN.p09.disableFailed
    push(message || zhCN.p09.disableFailed, 'danger')
  } finally {
    pendingName.value = ''
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="sp-page sp-p09">
    <PageHeader
      :eyebrow="zhCN.p09.eyebrow"
      :title="zhCN.p09.title"
      :description="zhCN.p09.description"
    >
      <template #meta>
        <span v-if="payload">
          <span class="sp-faint">{{ zhCN.p09.kernelApi }}</span>
          <span class="sp-p09__meta-value sp-mono">{{ payload.kernel_api }}</span>
        </span>
        <span v-if="payload">
          <span class="sp-faint">{{ zhCN.p09.gateMax }}</span>
          <span class="sp-p09__meta-value sp-mono">{{ payload.platform_gate_max }}</span>
        </span>
        <StatusBadge
          v-if="payload"
          :label="readonly ? zhCN.common.readonlyMode : zhCN.common.readonly"
          tone="neutral"
        />
      </template>
      <template #actions>
        <ElButton size="small" :loading="loading" @click="load">{{ zhCN.p09.refresh }}</ElButton>
      </template>
    </PageHeader>

    <StateView v-if="loading" state="loading" compact />
    <StateView
      v-else-if="forbidden"
      state="forbidden"
      :title="zhCN.states.forbidden"
      :description="zhCN.states.forbiddenHint"
      :retryable="false"
      compact
    />
    <StateView
      v-else-if="errorText"
      state="error"
      :title="zhCN.p09.loadFailed"
      :description="errorText"
      compact
      @retry="load"
    />

    <template v-else-if="payload">
      <div v-if="notice" class="sp-p09__notice" role="status">
        <span>{{ notice }}</span>
        <span class="sp-p09__notice-hint">{{ zhCN.p09.reloadHint }}</span>
      </div>

      <BlockingAlert :blocked="payload.blocked" />

      <section class="sp-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p09.modulesTitle }}</span>
            <span class="sp-panel__count">{{ payload.modules.length }}</span>
          </div>
          <span class="sp-panel__hint">{{ zhCN.p09.modulesHint }}</span>
        </div>
        <div class="sp-p09__panel-body">
          <ModuleList
            :modules="payload.modules"
            :can-disable="canDisable"
            :pending-name="pendingName"
            @disable="askDisable"
          />
        </div>
      </section>

      <section class="sp-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">{{ zhCN.p09.bundlesTitle }}</div>
          <span class="sp-panel__hint">{{ zhCN.p09.bundlesHint }}</span>
        </div>
        <div class="sp-p09__panel-body">
          <StateView
            v-if="!payload.bundles.length"
            state="empty"
            :title="zhCN.p09.emptyBundles"
            compact
          />
          <ul v-else class="sp-p09__bundles">
            <li v-for="(bundle, index) in payload.bundles" :key="index" class="sp-chip">
              {{ String(bundle) }}
            </li>
          </ul>
        </div>
      </section>
    </template>

    <ConfirmDialog
      :open="confirmOpen"
      :title="zhCN.p09.disableConfirmTitle"
      :body="selected ? zhCN.p09.disableConfirmBody(selected.name) : ''"
      :confirm-label="zhCN.p09.disable"
      :cancel-label="zhCN.common.cancel"
      danger
      :pending="Boolean(pendingName)"
      @confirm="confirmDisable"
      @cancel="cancelDisable"
    />
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p09__meta-value {
  margin-left: 5px;
  color: var(--sp-text);
}

.sp-p09__notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px 12px;
  padding: 7px 12px;
  border: 1px solid var(--sp-success-border);
  border-left: 3px solid var(--sp-success);
  border-radius: var(--sp-radius);
  background: var(--sp-success-soft);
  color: var(--sp-success);
  font-size: 12px;
  font-weight: 500;
}

.sp-p09__notice-hint {
  font-size: 10.5px;
  font-weight: 400;
  color: #406a56;
}

.sp-panel__hint {
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-p09__panel-body {
  padding: 12px;
}

.sp-p09__bundles {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
</style>
