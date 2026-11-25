<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElButton, ElOption, ElSelect, ElTable, ElTableColumn } from 'element-plus'

import {
  ApiError,
  createSubscription,
  deleteSubscription,
  fetchIdentityRoles,
  fetchNotificationTemplates,
  fetchSubscriptions,
} from '../api/client'
import type {
  NotificationTemplatesResponse,
  RolesResponse,
  Subscription,
  SubscriptionsResponse,
} from '../api/types'
import { CREDENTIALS_COPY, zhCN } from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useContextStore } from '../stores/context'
import { useToast } from '../composables/useToast'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

const EVENT_CODES = ['EVT-01', 'EVT-02', 'EVT-03', 'EVT-04', 'EVT-07'] as const

const session = useSessionStore()
const context = useContextStore()
const { push } = useToast()

const rolesPayload = ref<RolesResponse | null>(null)
const subscriptionsPayload = ref<SubscriptionsResponse | null>(null)
const templatesPayload = ref<NotificationTemplatesResponse | null>(null)
const loading = ref(true)
const errorText = ref('')
const submitting = ref(false)
const formError = ref('')
const deleteTarget = ref<Subscription | null>(null)
const deleteOpen = ref(false)
const deletePending = ref(false)

const form = reactive({
  name: '',
  event: 'EVT-01',
  receiver: '',
  channel: 'CONSOLE',
  window: zhCN.p12.form.windowDefault,
  thresholds: '',
  silent: '',
})

const role = computed(() => session.role || context.role)
const canManage = computed(() => role.value === 'OWNER' || role.value === 'EDITOR')
const isViewer = computed(() => role.value === 'VIEWER')
const roles = computed(() => rolesPayload.value?.roles ?? [])
const shops = computed(() => rolesPayload.value?.shops ?? [])
const subscriptions = computed(() => subscriptionsPayload.value?.items ?? [])
const channels = computed(() => subscriptionsPayload.value?.channels ?? [])
const templates = computed(() => templatesPayload.value?.items ?? [])
const emptySubscriptionsCopy = computed(
  () => subscriptionsPayload.value?.empty_copy || zhCN.p12.emptySubscriptions,
)
const windowOptions = computed(() =>
  context.windows.length ? context.windows : [zhCN.p12.form.windowDefault],
)
const deleteBody = computed(() =>
  deleteTarget.value ? zhCN.p12.deleteBody(deleteTarget.value.name) : '',
)

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError) return cause.userMessage || fallback
  if (cause && typeof cause === 'object' && 'userMessage' in cause) {
    return String((cause as { userMessage: unknown }).userMessage) || fallback
  }
  return fallback
}

function roleLabel(code: string): string {
  return zhCN.roles[code] ?? code
}

function permissionLabel(code: string): string {
  return zhCN.p12.permissionLabels[code] ?? code
}

function eventLabel(code: string): string {
  return zhCN.p12.eventLabels[code] ?? code
}

function channelLabel(code: string): string {
  return zhCN.p12.channelLabels[code] ?? code
}

function thresholdsText(value: Record<string, number>): string {
  const entries = Object.entries(value ?? {})
  if (!entries.length) return zhCN.common.none
  return entries.map(([key, item]) => `${key}: ${item}`).join('\n')
}

function subscriptionStatusLabel(enabled: boolean): string {
  return enabled ? zhCN.p12.subscriptionStatus.enabled : zhCN.p12.subscriptionStatus.disabled
}

function parseThresholds(raw: string): Record<string, number> | null {
  const text = raw.trim()
  if (!text) return {}
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    return null
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
  const result: Record<string, number> = {}
  for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return null
    result[key] = value
  }
  return result
}

function resetForm(): void {
  form.name = ''
  form.receiver = ''
  form.thresholds = ''
  form.silent = ''
  formError.value = ''
}

async function load(): Promise<void> {
  loading.value = true
  errorText.value = ''
  try {
    const [rolesResponse, subscriptionsResponse, templatesResponse] = await Promise.all([
      fetchIdentityRoles(),
      fetchSubscriptions(),
      fetchNotificationTemplates(),
    ])
    rolesPayload.value = rolesResponse
    subscriptionsPayload.value = subscriptionsResponse
    templatesPayload.value = templatesResponse
    if (subscriptionsResponse.channels.length && !subscriptionsResponse.channels.includes(form.channel)) {
      form.channel = subscriptionsResponse.channels[0]
    }
  } catch (cause) {
    errorText.value = errorMessage(cause, zhCN.p12.loadFailed)
  } finally {
    loading.value = false
  }
}

async function submit(): Promise<void> {
  if (!canManage.value || submitting.value) return
  formError.value = ''
  if (!form.name.trim() || !form.receiver.trim()) {
    formError.value = zhCN.p12.form.required
    return
  }
  const thresholds = parseThresholds(form.thresholds)
  if (thresholds === null) {
    formError.value = zhCN.p12.form.jsonInvalid
    return
  }
  submitting.value = true
  try {
    await createSubscription({
      name: form.name.trim(),
      event: form.event,
      receiver: form.receiver.trim(),
      channel: form.channel,
      window: form.window,
      thresholds,
      silent_window: form.silent.trim() || null,
    })
    push(zhCN.p12.form.success, 'success')
    resetForm()
    await load()
  } catch (cause) {
    const message =
      cause instanceof ApiError && cause.status === 409
        ? zhCN.p12.form.duplicate
        : errorMessage(cause, zhCN.p12.form.failed)
    formError.value = message
    push(message, 'danger')
  } finally {
    submitting.value = false
  }
}

function askDelete(item: unknown): void {
  if (!canManage.value) return
  deleteTarget.value = item as Subscription
  deleteOpen.value = true
}

function cancelDelete(): void {
  if (deletePending.value) return
  deleteOpen.value = false
  deleteTarget.value = null
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value
  if (!target) return
  deletePending.value = true
  try {
    await deleteSubscription(target.id)
    push(zhCN.p12.deleteSuccess, 'success')
    deleteOpen.value = false
    deleteTarget.value = null
    await load()
  } catch (cause) {
    push(errorMessage(cause, zhCN.p12.deleteFailed), 'danger')
  } finally {
    deletePending.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="sp-page sp-p12">
    <PageHeader
      :eyebrow="zhCN.p12.eyebrow"
      :title="zhCN.p12.title"
      :description="zhCN.p12.description"
    >
      <template #meta>
        <StatusBadge v-if="isViewer" :label="zhCN.p12.readonlyHint" tone="neutral" />
      </template>
      <template #actions>
        <ElButton size="small" :loading="loading" @click="load">{{ zhCN.p12.refresh }}</ElButton>
      </template>
    </PageHeader>

    <div class="sp-p12__credentials" role="note">{{ CREDENTIALS_COPY }}</div>

    <StateView v-if="loading" state="loading" compact />
    <StateView
      v-else-if="errorText"
      state="error"
      :title="zhCN.p12.loadFailed"
      :description="errorText"
      compact
      @retry="load"
    />

    <template v-else>
      <section class="sp-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">{{ zhCN.p12.rolesTitle }}</div>
          <span class="sp-panel__hint">{{ zhCN.p12.rolesHint }}</span>
        </div>
        <div class="sp-p12__roles">
          <article v-for="entry in roles" :key="entry.role" class="sp-role-card">
            <header class="sp-role-card__head">
              <span class="sp-role-card__name">{{ roleLabel(entry.role) }}</span>
              <span class="sp-chip sp-mono">{{ entry.role }}</span>
              <span class="sp-role-card__count">
                {{ zhCN.p12.permissionCount(entry.permissions.length) }}
              </span>
            </header>
            <div class="sp-role-card__perms">
              <span
                v-for="permission in entry.permissions"
                :key="permission"
                class="sp-chip"
                :title="permission"
              >
                {{ permissionLabel(permission) }}
                <span class="sp-mono sp-role-card__code">{{ permission }}</span>
              </span>
            </div>
          </article>
          <StateView v-if="!roles.length" state="empty" :title="zhCN.common.empty" compact />
        </div>
      </section>

      <section class="sp-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p12.shopsTitle }}</span>
            <span v-if="shops.length" class="sp-panel__count">{{ shops.length }}</span>
          </div>
          <span class="sp-panel__hint">{{ zhCN.p12.shopsHint }}</span>
        </div>
        <StateView v-if="!shops.length" state="empty" :title="zhCN.p12.shopsEmpty" compact />
        <ElTable v-else :data="shops" size="small" border style="width: 100%">
          <ElTableColumn prop="platform" :label="zhCN.p12.shopColumns.platform" width="140" />
          <ElTableColumn prop="shop_id" :label="zhCN.p12.shopColumns.shop" min-width="160">
            <template #default="{ row }">
              <span class="sp-mono">{{ row.shop_id }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p12.shopColumns.role" width="120">
            <template #default="{ row }">
              <StatusBadge :label="roleLabel(row.role)" tone="primary" />
            </template>
          </ElTableColumn>
        </ElTable>
      </section>

      <section v-if="canManage" class="sp-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">{{ zhCN.p12.createTitle }}</div>
          <span class="sp-panel__hint">{{ zhCN.p12.createHint }}</span>
        </div>
        <div class="sp-p12__form">
          <label class="sp-field">
            <span class="sp-field__label">{{ zhCN.p12.form.name }}</span>
            <input
              v-model="form.name"
              class="sp-field__control"
              type="text"
              :placeholder="zhCN.p12.form.namePlaceholder"
              :disabled="submitting"
            />
          </label>
          <label class="sp-field">
            <span class="sp-field__label">{{ zhCN.p12.form.receiver }}</span>
            <input
              v-model="form.receiver"
              class="sp-field__control"
              type="text"
              :placeholder="zhCN.p12.form.receiverPlaceholder"
              :disabled="submitting"
            />
          </label>
          <label class="sp-field">
            <span class="sp-field__label">{{ zhCN.p12.form.event }}</span>
            <ElSelect v-model="form.event" size="small" :disabled="submitting">
              <ElOption
                v-for="code in EVENT_CODES"
                :key="code"
                :label="`${eventLabel(code)} · ${code}`"
                :value="code"
              />
            </ElSelect>
          </label>
          <label class="sp-field">
            <span class="sp-field__label">{{ zhCN.p12.form.channel }}</span>
            <ElSelect v-model="form.channel" size="small" :disabled="submitting">
              <ElOption
                v-for="code in channels"
                :key="code"
                :label="channelLabel(code)"
                :value="code"
              />
            </ElSelect>
          </label>
          <label class="sp-field">
            <span class="sp-field__label">{{ zhCN.p12.form.window }}</span>
            <ElSelect v-model="form.window" size="small" :disabled="submitting">
              <ElOption v-for="item in windowOptions" :key="item" :label="item" :value="item" />
            </ElSelect>
          </label>
          <label class="sp-field">
            <span class="sp-field__label">{{ zhCN.p12.form.silent }}</span>
            <input
              v-model="form.silent"
              class="sp-field__control"
              type="text"
              :placeholder="zhCN.p12.form.silentPlaceholder"
              :disabled="submitting"
            />
          </label>
          <label class="sp-field sp-field--wide">
            <span class="sp-field__label">{{ zhCN.p12.form.thresholds }}</span>
            <textarea
              v-model="form.thresholds"
              class="sp-field__control sp-field__control--textarea"
              rows="2"
              :placeholder="zhCN.p12.form.thresholdsPlaceholder"
              :disabled="submitting"
            />
          </label>
          <div class="sp-p12__form-actions">
            <p v-if="formError" class="sp-p12__form-error" role="alert">{{ formError }}</p>
            <div class="sp-p12__form-buttons">
              <ElButton size="small" :disabled="submitting" @click="resetForm">
                {{ zhCN.p12.form.cancel }}
              </ElButton>
              <ElButton size="small" type="primary" :loading="submitting" @click="submit">
                {{ submitting ? zhCN.p12.form.submitting : zhCN.p12.form.submit }}
              </ElButton>
            </div>
          </div>
        </div>
      </section>

      <section v-if="!canManage" class="sp-p12__readonly" role="note">
        {{ zhCN.p12.readonlyHint }}
      </section>

      <section class="sp-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p12.subscriptionsTitle }}</span>
            <span v-if="subscriptions.length" class="sp-panel__count">{{ subscriptions.length }}</span>
          </div>
          <span class="sp-panel__hint">{{ zhCN.p12.subscriptionsHint }}</span>
        </div>
        <StateView
          v-if="!subscriptions.length"
          state="empty"
          :title="emptySubscriptionsCopy"
          :description="zhCN.p12.emptySubscriptionsHint"
          compact
        />
        <ElTable v-else :data="subscriptions" size="small" border style="width: 100%">
          <ElTableColumn prop="name" :label="zhCN.p12.subscriptionColumns.name" min-width="130" />
          <ElTableColumn :label="zhCN.p12.subscriptionColumns.event" width="118">
            <template #default="{ row }">
              <span class="sp-mono">{{ row.event }}</span>
              <span class="sp-p12__event-label">{{ eventLabel(row.event) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="receiver" :label="zhCN.p12.subscriptionColumns.receiver" width="110" />
          <ElTableColumn :label="zhCN.p12.subscriptionColumns.channel" width="96">
            <template #default="{ row }">{{ channelLabel(row.channel) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="window" :label="zhCN.p12.subscriptionColumns.window" width="88" />
          <ElTableColumn :label="zhCN.p12.subscriptionColumns.thresholds" min-width="150">
            <template #default="{ row }">
              <span class="sp-p12__thresholds sp-mono">{{ thresholdsText(row.thresholds) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p12.subscriptionColumns.silent" width="116">
            <template #default="{ row }">{{ row.silent_window || zhCN.common.none }}</template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p12.subscriptionColumns.status" width="90">
            <template #default="{ row }">
              <StatusBadge
                :label="subscriptionStatusLabel(row.enabled)"
                :tone="row.enabled ? 'success' : 'neutral'"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn
            v-if="canManage"
            :label="zhCN.p12.subscriptionColumns.actions"
            width="82"
            fixed="right"
          >
            <template #default="{ row }">
              <ElButton size="small" @click.stop="askDelete(row)">
                {{ zhCN.p12.delete }}
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>

      <section class="sp-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p12.templatesTitle }}</span>
            <span v-if="templates.length" class="sp-panel__count">{{ templates.length }}</span>
          </div>
          <span class="sp-panel__hint">{{ zhCN.p12.templatesHint }}</span>
        </div>
        <StateView v-if="!templates.length" state="empty" :title="zhCN.p12.templatesEmpty" compact />
        <ElTable v-else :data="templates" size="small" border style="width: 100%">
          <ElTableColumn :label="zhCN.p12.templateColumns.event" width="104">
            <template #default="{ row }">
              <span class="sp-mono">{{ row.event }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="title" :label="zhCN.p12.templateColumns.title" min-width="150" />
          <ElTableColumn :label="zhCN.p12.templateColumns.body" min-width="260">
            <template #default="{ row }">
              <span class="sp-p12__template-body" :title="row.body">{{ row.body }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="module" :label="zhCN.p12.templateColumns.module" width="150">
            <template #default="{ row }">
              <span class="sp-mono">{{ row.module }}</span>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>
    </template>

    <ConfirmDialog
      :open="deleteOpen"
      :title="zhCN.p12.deleteTitle"
      :body="deleteBody"
      :confirm-label="zhCN.p12.deleteConfirm"
      :cancel-label="zhCN.common.cancel"
      danger
      :pending="deletePending"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p12__credentials {
  padding: 6px 11px;
  border: 1px solid var(--sp-warning-border);
  border-left: 3px solid var(--sp-warning);
  border-radius: var(--sp-radius);
  background: var(--sp-warning-soft);
  color: var(--sp-warning);
  font-size: 11.5px;
}

.sp-p12__roles {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
}

.sp-role-card {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
}

.sp-role-card__head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px;
}

.sp-role-card__name {
  font-size: 13px;
  font-weight: 650;
  color: var(--sp-text);
  margin-right: auto;
}

.sp-role-card__count {
  flex-basis: 100%;
  font-size: 10px;
  color: var(--sp-faint);
}

.sp-role-card__perms {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.sp-role-card__code {
  margin-left: 4px;
  font-size: 9px;
  color: var(--sp-faint);
}

.sp-p12__form {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 12px;
  padding: 12px;
}

.sp-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.sp-field--wide {
  grid-column: span 2;
}

.sp-field__label {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-field__control {
  width: 100%;
  height: 30px;
  padding: 0 9px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  font-size: 12.5px;
  color: var(--sp-text);
}

.sp-field__control--textarea {
  height: auto;
  min-height: 50px;
  padding: 6px 9px;
  line-height: 1.5;
  resize: vertical;
}

.sp-field__control:focus {
  outline: none;
  border-color: var(--sp-primary);
  box-shadow: var(--sp-focus);
}

.sp-p12__form-actions {
  display: flex;
  grid-column: 1 / -1;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.sp-p12__form-error {
  font-size: 11.5px;
  color: var(--sp-danger);
}

.sp-p12__form-buttons {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.sp-p12__readonly {
  padding: 6px 11px;
  border: 1px solid var(--sp-readonly-border);
  border-left: 3px solid var(--sp-readonly);
  border-radius: var(--sp-radius);
  background: var(--sp-readonly-soft);
  color: var(--sp-readonly);
  font-size: 11.5px;
}

.sp-p12__event-label {
  display: block;
  font-size: 9.5px;
  color: var(--sp-faint);
}

.sp-p12__thresholds {
  display: block;
  white-space: pre-wrap;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-p12__template-body {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--sp-muted);
}

@media (max-width: 1080px) {
  .sp-p12__roles {
    grid-template-columns: minmax(0, 1fr);
  }
  .sp-p12__form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .sp-field--wide {
    grid-column: span 2;
  }
}

@media (max-width: 680px) {
  .sp-p12__form {
    grid-template-columns: minmax(0, 1fr);
  }
  .sp-field--wide {
    grid-column: span 1;
  }
}
</style>
