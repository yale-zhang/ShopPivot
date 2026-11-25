<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElButton } from 'element-plus'

import { ApiError, createWritePlan, fetchPlatformPriceList } from '../api/client'
import type {
  CreateWritePlanRequest,
  CreateWritePlanRow,
  PlatformPriceListResponse,
  WritePlanCreateResponse,
} from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import StateView from './StateView.vue'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'created', payload: WritePlanCreateResponse): void
}>()

type ActionCode = 'S02.price_update' | 'S03.campaign_apply'

interface DraftRow {
  key: number
  sku: string
  after: string
  campaignId: string
  activityPrice: string
}

let rowSeq = 0

function makeRow(): DraftRow {
  rowSeq += 1
  return { key: rowSeq, sku: '', after: '', campaignId: '', activityPrice: '' }
}

const actionCode = ref<ActionCode>('S02.price_update')
const rows = ref<DraftRow[]>([makeRow()])
const priceList = ref<PlatformPriceListResponse | null>(null)
const priceLoading = ref(false)
const priceError = ref('')
const submitError = ref('')
const pending = ref(false)

const isCampaign = computed(() => actionCode.value === 'S03.campaign_apply')
const skuOptions = computed(() => priceList.value?.items ?? [])
const campaignSuggestions = computed(() => priceList.value?.campaign_suggestions ?? [])
const demoNote = computed(
  () => priceList.value?.note || zhCN.p05.create.demoNote,
)

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError) return cause.message || cause.userMessage || fallback
  if (cause && typeof cause === 'object') {
    if ('message' in cause && typeof cause.message === 'string' && cause.message) {
      return cause.message
    }
    if ('userMessage' in cause) {
      const message = String((cause as { userMessage: unknown }).userMessage)
      if (message) return message
    }
  }
  return fallback
}

function currentPrice(sku: string): string {
  const item = skuOptions.value.find((entry) => entry.sku === sku)
  return item ? item.price : ''
}

function text(value: unknown): string {
  if (typeof value === 'string') return value
  if (value === null || value === undefined) return ''
  return String(value)
}

function positive(value: unknown): boolean {
  const trimmed = text(value).trim()
  if (!trimmed) return false
  const number = Number(trimmed)
  return Number.isFinite(number) && number > 0
}

function validate(): string {
  if (!rows.value.length) return zhCN.p05.create.rowsRequired
  for (const row of rows.value) {
    if (!row.sku) return zhCN.p05.create.skuRequired
    if (isCampaign.value) {
      if (!text(row.campaignId).trim()) return zhCN.p05.create.campaignRequired
      if (!positive(row.activityPrice)) return zhCN.p05.create.priceRequired
    } else if (!positive(row.after)) {
      return zhCN.p05.create.priceRequired
    }
  }
  return ''
}

function buildRows(): CreateWritePlanRow[] {
  if (isCampaign.value) {
    return rows.value.map((row) => ({
      campaign_id: text(row.campaignId).trim(),
      sku: row.sku,
      activity_price: text(row.activityPrice).trim(),
    }))
  }
  return rows.value.map((row) => ({ sku: row.sku, after: text(row.after).trim() }))
}

async function loadPriceList(): Promise<void> {
  priceLoading.value = true
  priceError.value = ''
  try {
    priceList.value = await fetchPlatformPriceList()
  } catch (cause) {
    priceError.value = errorMessage(cause, zhCN.p05.create.priceListFailed)
  } finally {
    priceLoading.value = false
  }
}

function addRow(): void {
  rows.value = [...rows.value, makeRow()]
  void nextTick(() => {
    const controls = document.querySelectorAll<HTMLElement>('[data-create-row] select')
    controls[controls.length - 1]?.focus()
  })
}

function removeRow(index: number): void {
  if (rows.value.length <= 1) return
  rows.value = rows.value.filter((_, position) => position !== index)
}

async function submit(): Promise<void> {
  if (pending.value) return
  submitError.value = ''
  const message = validate()
  if (message) {
    submitError.value = message
    return
  }
  const action = actionCode.value
  const payload: CreateWritePlanRequest = {
    action_code: action,
    platform: 'demo',
    shop_id: 'SHOP-0001',
    rows: buildRows(),
    idempotency_key: `ui-${action.split('.')[0]}-${Date.now()}`,
    scene: action.split('.')[0],
  }
  pending.value = true
  try {
    const result = await createWritePlan(payload)
    emit('created', result)
  } catch (cause) {
    submitError.value = errorMessage(cause, zhCN.p05.create.submitFailed)
  } finally {
    pending.value = false
  }
}

function cancel(): void {
  if (pending.value) return
  emit('close')
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && !pending.value) {
    event.stopPropagation()
    cancel()
  }
}

watch(
  () => props.open,
  (open) => {
    if (typeof document === 'undefined') return
    if (open) {
      actionCode.value = 'S02.price_update'
      rows.value = [makeRow()]
      submitError.value = ''
      pending.value = false
      document.addEventListener('keydown', onKeydown)
      void loadPriceList()
    } else {
      document.removeEventListener('keydown', onKeydown)
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (typeof document === 'undefined') return
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="sp-create">
      <div v-if="open" class="sp-create-root" :style="{ zIndex: 2200 }">
        <div class="sp-create__overlay" aria-hidden="true" @click="cancel" />
        <div
          class="sp-create"
          role="dialog"
          aria-modal="true"
          :aria-label="zhCN.p05.create.title"
          data-dialog="create-change-order"
        >
          <header class="sp-create__head">
            <h2 class="sp-create__title">{{ zhCN.p05.create.title }}</h2>
            <button
              type="button"
              class="sp-create__close"
              :aria-label="zhCN.p05.create.close"
              :title="zhCN.p05.create.close"
              :disabled="pending"
              @click="cancel"
            >
              ×
            </button>
          </header>
          <p class="sp-create__description">{{ zhCN.p05.create.description }}</p>

          <label class="sp-create__field">
            <span class="sp-create__label">{{ zhCN.p05.create.actionLabel }}</span>
            <select v-model="actionCode" class="sp-create__control" data-field="action_code">
              <option value="S02.price_update">{{ zhCN.p05.create.actionS02 }}</option>
              <option value="S03.campaign_apply">{{ zhCN.p05.create.actionS03 }}</option>
            </select>
          </label>

          <StateView v-if="priceLoading" state="loading" compact />
          <StateView
            v-else-if="priceError"
            state="error"
            :title="zhCN.p05.create.priceListFailed"
            :description="priceError"
            compact
            @retry="loadPriceList"
          />
          <div v-else class="sp-create__rows">
            <div
              v-for="(row, index) in rows"
              :key="row.key"
              class="sp-create__row"
              data-create-row
            >
              <div class="sp-create__row-head">
                <span class="sp-create__row-title">
                  {{ zhCN.p05.create.rowTitle.replace('{index}', String(index + 1)) }}
                </span>
                <button
                  v-if="rows.length > 1"
                  type="button"
                  class="sp-link-btn"
                  :disabled="pending"
                  @click="removeRow(index)"
                >
                  {{ zhCN.p05.create.removeRow }}
                </button>
              </div>

              <label v-if="isCampaign" class="sp-create__field">
                <span class="sp-create__label">{{ zhCN.p05.create.campaignLabel }}</span>
                <input
                  v-model="row.campaignId"
                  class="sp-create__control"
                  type="text"
                  list="sp-campaign-suggestions"
                  data-field="campaign_id"
                  :placeholder="zhCN.p05.create.campaignPlaceholder"
                  :disabled="pending"
                />
                <span v-if="campaignSuggestions.length" class="sp-create__suggestions">
                  <span class="sp-create__suggestions-label">
                    {{ zhCN.p05.create.campaignSuggestions }}
                  </span>
                  <button
                    v-for="campaign in campaignSuggestions"
                    :key="campaign"
                    type="button"
                    class="sp-chip"
                    :disabled="pending"
                    @click="row.campaignId = campaign"
                  >
                    {{ campaign }}
                  </button>
                </span>
              </label>

              <label class="sp-create__field">
                <span class="sp-create__label">{{ zhCN.p05.create.skuLabel }}</span>
                <select v-model="row.sku" class="sp-create__control" data-field="sku" :disabled="pending">
                  <option value="">{{ zhCN.p05.create.skuPlaceholder }}</option>
                  <option v-for="item in skuOptions" :key="item.sku" :value="item.sku">
                    {{ item.sku }} · {{ item.price }}
                  </option>
                </select>
              </label>

              <p v-if="row.sku && !isCampaign" class="sp-create__hint sp-mono">
                {{ zhCN.p05.create.currentPrice }} · {{ currentPrice(row.sku) || zhCN.common.none }}
              </p>

              <label class="sp-create__field">
                <span class="sp-create__label">
                  {{ isCampaign ? zhCN.p05.create.activityPriceLabel : zhCN.p05.create.targetPriceLabel }}
                </span>
                <input
                  v-if="isCampaign"
                  v-model="row.activityPrice"
                  class="sp-create__control"
                  type="text"
                  inputmode="decimal"
                  data-field="activity_price"
                  :placeholder="zhCN.p05.create.activityPricePlaceholder"
                  :disabled="pending"
                />
                <input
                  v-else
                  v-model="row.after"
                  class="sp-create__control"
                  type="text"
                  inputmode="decimal"
                  data-field="after"
                  :placeholder="zhCN.p05.create.targetPricePlaceholder"
                  :disabled="pending"
                />
              </label>
            </div>

            <datalist id="sp-campaign-suggestions">
              <option v-for="campaign in campaignSuggestions" :key="campaign" :value="campaign" />
            </datalist>

            <div class="sp-create__row-actions">
              <ElButton size="small" :disabled="pending" @click="addRow">
                {{ zhCN.p05.create.addRow }}
              </ElButton>
            </div>

            <p class="sp-create__demo">{{ demoNote }}</p>
          </div>

          <p v-if="submitError" class="sp-create__error" role="alert" data-role="create-error">
            {{ submitError }}
          </p>

          <footer class="sp-create__footer">
            <ElButton size="small" :disabled="pending" @click="cancel">
              {{ zhCN.p05.create.cancel }}
            </ElButton>
            <ElButton
              size="small"
              type="primary"
              :loading="pending"
              :disabled="pending || priceLoading || Boolean(priceError)"
              data-action="submit-create-order"
              @click="submit"
            >
              {{ pending ? zhCN.p05.create.submitting : zhCN.p05.create.submit }}
            </ElButton>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.sp-create-root {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.sp-create__overlay {
  position: absolute;
  inset: 0;
  background: rgba(31, 42, 48, 0.38);
}

.sp-create {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(560px, 100%);
  max-height: calc(100vh - 48px);
  overflow: auto;
  padding: 16px;
  background: var(--sp-surface);
  border: 1px solid var(--sp-border-strong);
  border-radius: var(--sp-radius);
  box-shadow: var(--sp-shadow-modal);
}

.sp-create__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.sp-create__title {
  font-size: 14px;
  font-weight: 650;
  color: var(--sp-text);
}

.sp-create__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  color: var(--sp-muted);
  font-size: 16px;
  line-height: 1;
  flex: none;
}

.sp-create__close:hover {
  border-color: var(--sp-border-strong);
  color: var(--sp-text);
}

.sp-create__description {
  font-size: 12px;
  line-height: 1.6;
  color: var(--sp-muted);
}

.sp-create__rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sp-create__row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 9px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
}

.sp-create__row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.sp-create__row-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-create__row-actions {
  display: flex;
  justify-content: flex-start;
}

.sp-create__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sp-create__label {
  font-size: 11px;
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-create__control {
  width: 100%;
  height: 30px;
  padding: 0 9px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  font-size: 12.5px;
  color: var(--sp-text);
}

.sp-create__control:focus {
  border-color: var(--sp-primary);
  outline: none;
}

.sp-create__hint {
  font-size: 11px;
  color: var(--sp-faint);
}

.sp-create__suggestions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.sp-create__suggestions-label {
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-create__suggestions .sp-chip {
  cursor: pointer;
}

.sp-create__suggestions .sp-chip:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.sp-create__demo {
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-create__error {
  padding: 6px 9px;
  border: 1px solid var(--sp-danger-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-danger-soft);
  color: var(--sp-danger);
  font-size: 12px;
}

.sp-create__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px solid var(--sp-border);
}

.sp-create-enter-active,
.sp-create-leave-active {
  transition: opacity 140ms ease;
}
</style>
