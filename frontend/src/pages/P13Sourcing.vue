<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElTable, ElTableColumn } from 'element-plus'

import {
  ApiError,
  createPurchasePlan,
  fetchPurchases,
  fetchSourcingProvider,
  refreshPurchase,
  searchSourcing,
} from '../api/client'
import type {
  PurchaseOrder,
  PurchasesResponse,
  SourcingCandidate,
  SourcingProviderResponse,
  SourcingSearchResponse,
} from '../api/types'
import {
  EMPTY_CANDIDATES_COPY,
  EMPTY_PURCHASES_COPY,
  zhCN,
  type Tone,
} from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useContextStore } from '../stores/context'
import { useToast } from '../composables/useToast'
import { formatDateTime, formatNumber, truncateHead } from '../utils/format'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

const router = useRouter()
const session = useSessionStore()
const context = useContextStore()
const { push } = useToast()

const provider = ref<SourcingProviderResponse | null>(null)
const providerLoading = ref(true)
const providerError = ref('')

const keyword = ref('')
const searching = ref(false)
const searchError = ref('')
const result = ref<SourcingSearchResponse | null>(null)

const freeShippingOnly = ref(false)
const hasSalesOnly = ref(false)
const priceMin = ref('')
const priceMax = ref('')

const selectedOfferId = ref('')
const quantity = ref('1')
const creating = ref(false)
const createError = ref('')

const purchases = ref<PurchasesResponse | null>(null)
const purchasesLoading = ref(true)
const purchasesError = ref('')
const refreshingPlanId = ref('')
const refreshNote = ref('')

let searchSeq = 0
let purchasesSeq = 0

const role = computed(() => session.role || context.role)
const canCreate = computed(() => role.value === 'OWNER' || role.value === 'EDITOR')
const isViewer = computed(() => role.value === 'VIEWER')

const candidates = computed<SourcingCandidate[]>(() => result.value?.candidates ?? [])
const orders = computed<PurchaseOrder[]>(() => purchases.value?.items ?? [])

const providerModeLabel = computed(() => {
  const mode = provider.value?.mode ?? ''
  if (!mode) return zhCN.p13.providerModeUnknown
  return zhCN.p13.providerModes[mode] ?? mode
})

const providerNote = computed(
  () => provider.value?.note || zhCN.p13.providerNoteFallback,
)

const candidateEmptyCopy = computed(
  () => result.value?.empty_copy || EMPTY_CANDIDATES_COPY,
)
const purchaseEmptyCopy = computed(
  () => purchases.value?.empty_copy || EMPTY_PURCHASES_COPY,
)

/** 后端 Decimal 以字符串返回；前端统一转数字展示，不改变原值。 */
function amountOf(value: number | string | null | undefined): number {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0
  const parsed = Number(value ?? '')
  return Number.isFinite(parsed) ? parsed : 0
}

function money(value: number | string | null | undefined): string {
  return formatNumber(amountOf(value), 2)
}

function postFeeText(value: number | string | null | undefined): string {
  if (amountOf(value) === 0) return zhCN.p13.candidates.freeShipping
  return zhCN.p13.candidates.postFee(money(value))
}

function matchesLocalFilters(row: SourcingCandidate): boolean {
  if (freeShippingOnly.value && amountOf(row.post_fee) !== 0) return false
  if (hasSalesOnly.value && amountOf(row.sales_30d) <= 0) return false
  const minText = priceMin.value.trim()
  const maxText = priceMax.value.trim()
  const min = minText ? Number(minText) : null
  const max = maxText ? Number(maxText) : null
  const price = amountOf(row.price)
  if (min !== null && Number.isFinite(min) && price < min) return false
  if (max !== null && Number.isFinite(max) && price > max) return false
  return true
}

const filteredCandidates = computed(() => candidates.value.filter(matchesLocalFilters))

const selectedCandidate = computed<SourcingCandidate | null>(
  () => candidates.value.find((row) => row.offer_id === selectedOfferId.value) ?? null,
)

const estimateTotal = computed(() => {
  const row = selectedCandidate.value
  if (!row) return ''
  const quantityNumber = Number(quantity.value)
  if (!Number.isFinite(quantityNumber) || quantityNumber <= 0) return ''
  return money(amountOf(row.price) * quantityNumber + amountOf(row.post_fee))
})

const BRAND_RISK_FLAG = zhCN.p13.riskBrandFlag

function riskFlags(row: unknown): string[] {
  const candidate = row as SourcingCandidate
  const flags = Array.isArray(candidate.risk_flags) ? [...candidate.risk_flags] : []
  if (!candidate.brand_authorized && !flags.includes(BRAND_RISK_FLAG)) {
    flags.push(BRAND_RISK_FLAG)
  }
  return flags
}

function riskLabel(flag: string): string {
  return zhCN.p13.riskLabels[flag] ?? flag
}

function isBrandRisk(flag: string): boolean {
  return flag === BRAND_RISK_FLAG
}

function purchaseStatusLabel(row: unknown): string {
  const order = row as PurchaseOrder
  return order.status_label || zhCN.p13.purchaseStatus[order.status] || order.status
}

function purchaseStatusTone(status: string): Tone {
  if (status === 'PAID') return 'success'
  if (status === 'FAILED') return 'danger'
  if (status === 'CANCELLED') return 'neutral'
  if (status.startsWith('AWAITING_')) return 'warning'
  return 'neutral'
}

function isAwaiting(status: string): boolean {
  return status.startsWith('AWAITING_')
}

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError) return cause.userMessage || fallback
  if (cause && typeof cause === 'object' && 'userMessage' in cause) {
    return String((cause as { userMessage: unknown }).userMessage) || fallback
  }
  return fallback
}

async function loadProvider(): Promise<void> {
  providerLoading.value = true
  providerError.value = ''
  try {
    provider.value = await fetchSourcingProvider()
  } catch (cause) {
    providerError.value = errorMessage(cause, zhCN.p13.providerLoadFailed)
  } finally {
    providerLoading.value = false
  }
}

async function loadPurchases(): Promise<void> {
  const seq = ++purchasesSeq
  purchasesLoading.value = true
  purchasesError.value = ''
  try {
    const response = await fetchPurchases()
    if (seq !== purchasesSeq) return
    purchases.value = response
  } catch (cause) {
    if (seq !== purchasesSeq) return
    purchasesError.value = errorMessage(cause, zhCN.p13.orders.loadFailed)
  } finally {
    if (seq === purchasesSeq) purchasesLoading.value = false
  }
}

function refreshAll(): void {
  void loadProvider()
  void loadPurchases()
}

async function runSearch(): Promise<void> {
  const value = keyword.value.trim()
  if (!value) {
    searchError.value = zhCN.p13.search.keywordRequired
    return
  }
  const seq = ++searchSeq
  searching.value = true
  searchError.value = ''
  createError.value = ''
  selectedOfferId.value = ''
  try {
    const response = await searchSourcing({ keyword: value, limit: 20, filters: [] })
    if (seq !== searchSeq) return
    result.value = response
    if (response.status === 'FAILED') {
      searchError.value = [zhCN.p13.search.failed, response.err_code, response.err_layer]
        .filter(Boolean)
        .join(' · ')
    }
  } catch (cause) {
    if (seq !== searchSeq) return
    result.value = null
    searchError.value = errorMessage(cause, zhCN.p13.search.failed)
  } finally {
    if (seq === searchSeq) searching.value = false
  }
}

function resetFilters(): void {
  freeShippingOnly.value = false
  hasSalesOnly.value = false
  priceMin.value = ''
  priceMax.value = ''
}

function selectCandidate(row: unknown): void {
  const candidate = row as SourcingCandidate
  if (!candidate || !candidate.offer_id) return
  if (selectedOfferId.value === candidate.offer_id) return
  selectedOfferId.value = candidate.offer_id
  quantity.value = String(candidate.moq ?? 1)
  createError.value = ''
}

async function submitPurchase(): Promise<void> {
  const row = selectedCandidate.value
  if (!row || !canCreate.value || creating.value) return
  const quantityNumber = Number(quantity.value)
  const moq = amountOf(row.moq)
  if (!Number.isInteger(quantityNumber) || quantityNumber < moq || moq < 1) {
    createError.value = zhCN.p13.purchase.quantityInvalid(moq)
    return
  }
  creating.value = true
  createError.value = ''
  try {
    const response = await createPurchasePlan({
      action_code: 'S11.purchase_order',
      platform: 'demo',
      shop_id: 'SHOP-0001',
      rows: [{ offer_id: row.offer_id, quantity: quantityNumber }],
      idempotency_key: `ui-p13-${Date.now()}`,
      scene: 'S11',
    })
    push(zhCN.p13.purchase.createSuccess, 'success')
    const taskId = response.task_id
    if (taskId) {
      void router.push(`/change-orders/${encodeURIComponent(taskId)}`)
      return
    }
    await loadPurchases()
  } catch (cause) {
    createError.value = errorMessage(cause, zhCN.p13.purchase.createFailed)
    push(createError.value, 'danger')
  } finally {
    creating.value = false
  }
}

async function refreshOrder(row: unknown): Promise<void> {
  const target = row as PurchaseOrder
  if (refreshingPlanId.value) return
  refreshingPlanId.value = target.plan_id
  try {
    const updated = await refreshPurchase(target.plan_id)
    const { note: refreshedNote, ...order } = updated
    refreshNote.value = refreshedNote || ''
    const list = purchases.value
    if (list) {
      purchases.value = {
        ...list,
        items: list.items.map((item) =>
          item.plan_id === order.plan_id ? { ...item, ...order } : item,
        ),
      }
    }
    push(zhCN.p13.orders.refreshSuccess, 'success')
  } catch (cause) {
    push(errorMessage(cause, zhCN.p13.orders.refreshFailed), 'danger')
  } finally {
    refreshingPlanId.value = ''
  }
}

onMounted(() => {
  void loadProvider()
  void loadPurchases()
})
</script>

<template>
  <div class="sp-page sp-p13">
    <PageHeader
      :eyebrow="zhCN.p13.eyebrow"
      :title="zhCN.p13.title"
      :description="zhCN.p13.description"
    >
      <template #meta>
        <span v-if="result?.run_id">
          <span class="sp-faint">{{ zhCN.status.runId }}</span>
          <span class="sp-p13__meta sp-mono">{{ result.run_id }}</span>
        </span>
        <span v-if="provider">
          <span class="sp-faint">{{ zhCN.p13.providerSourcing }}</span>
          <span class="sp-p13__meta sp-mono">{{ provider.sourcing_provider }}</span>
        </span>
        <StatusBadge v-if="isViewer" :label="zhCN.p13.readonlyHint" tone="neutral" />
      </template>
      <template #actions>
        <ElButton size="small" :loading="providerLoading || purchasesLoading" @click="refreshAll">
          {{ zhCN.p13.refresh }}
        </ElButton>
      </template>
    </PageHeader>

    <section class="sp-p13__provider" data-p13="provider" role="note">
      <div class="sp-p13__provider-head">
        <span class="sp-p13__provider-title">{{ zhCN.p13.providerTitle }}</span>
        <StatusBadge
          v-if="provider"
          :label="providerModeLabel"
          :tone="provider.mode === 'cli' ? 'info' : 'neutral'"
        />
        <StatusBadge v-else-if="providerLoading" :label="zhCN.common.loading" tone="neutral" />
      </div>
      <StateView
        v-if="providerError"
        state="error"
        :title="zhCN.p13.providerLoadFailed"
        :description="providerError"
        compact
        @retry="loadProvider"
      />
      <div v-else-if="provider" class="sp-p13__provider-body">
        <span class="sp-p13__provider-item">
          <span class="sp-faint">{{ zhCN.p13.providerSourcing }}</span>
          <span class="sp-mono">{{ provider.sourcing_provider }}</span>
        </span>
        <span class="sp-p13__provider-item">
          <span class="sp-faint">{{ zhCN.p13.providerPurchase }}</span>
          <span class="sp-mono">{{ provider.purchase_provider }}</span>
        </span>
        <span class="sp-chip sp-chip--primary">{{ zhCN.p13.humanLoop }}</span>
        <span class="sp-p13__provider-note">{{ providerNote }}</span>
      </div>
    </section>

    <div class="sp-p13__boundary" role="note" data-p13="boundary">
      <span class="sp-p13__boundary-label">{{ zhCN.p13.boundaryLabel }}</span>
      <span>{{ zhCN.p13.boundary }}</span>
    </div>

    <section class="sp-panel sp-p13__search">
      <div class="sp-panel__header">
        <div class="sp-panel__title">{{ zhCN.p13.search.title }}</div>
        <span class="sp-panel__hint">{{ zhCN.p13.search.hint }}</span>
      </div>
      <div class="sp-p13__search-body">
        <label class="sp-p13__field sp-p13__field--grow">
          <span class="sp-p13__label">{{ zhCN.p13.search.keyword }}</span>
          <input
            v-model="keyword"
            class="sp-p13__control"
            type="text"
            data-field="sourcing-keyword"
            :placeholder="zhCN.p13.search.keywordPlaceholder"
            :disabled="searching"
            @keyup.enter="runSearch"
          />
        </label>
        <ElButton
          size="small"
          type="primary"
          data-action="sourcing-search"
          :loading="searching"
          @click="runSearch"
        >
          {{ searching ? zhCN.p13.search.searching : zhCN.p13.search.submit }}
        </ElButton>
      </div>
      <div class="sp-p13__filters" data-p13="local-filters">
        <span class="sp-p13__filters-title">{{ zhCN.p13.search.filtersTitle }}</span>
        <label class="sp-p13__check">
          <input v-model="freeShippingOnly" type="checkbox" data-filter="free-shipping" />
          <span>{{ zhCN.p13.search.freeShipping }}</span>
        </label>
        <label class="sp-p13__check">
          <input v-model="hasSalesOnly" type="checkbox" data-filter="has-sales" />
          <span>{{ zhCN.p13.search.hasSales }}</span>
        </label>
        <label class="sp-p13__price">
          <span class="sp-p13__label">{{ zhCN.p13.search.priceMin }}</span>
          <input
            v-model="priceMin"
            class="sp-p13__control sp-p13__control--price"
            type="number"
            min="0"
            data-filter="price-min"
            :placeholder="zhCN.p13.search.priceMinPlaceholder"
          />
        </label>
        <label class="sp-p13__price">
          <span class="sp-p13__label">{{ zhCN.p13.search.priceMax }}</span>
          <input
            v-model="priceMax"
            class="sp-p13__control sp-p13__control--price"
            type="number"
            min="0"
            data-filter="price-max"
            :placeholder="zhCN.p13.search.priceMaxPlaceholder"
          />
        </label>
        <button type="button" class="sp-link-btn" data-action="reset-filters" @click="resetFilters">
          {{ zhCN.p13.search.resetFilters }}
        </button>
        <span class="sp-p13__filters-hint">{{ zhCN.p13.search.filtersHint }}</span>
      </div>
      <div v-if="searchError" class="sp-p13__error" role="alert">{{ searchError }}</div>
    </section>

    <section class="sp-panel sp-p13__candidates" data-p13="candidates">
      <div class="sp-panel__header">
        <div class="sp-panel__title">
          <span>{{ zhCN.p13.candidates.title }}</span>
          <span v-if="filteredCandidates.length" class="sp-panel__count">
            {{ filteredCandidates.length }}
          </span>
        </div>
        <span class="sp-panel__hint">{{ zhCN.p13.candidates.hint }}</span>
      </div>
      <StateView
        v-if="!result"
        state="empty"
        :title="zhCN.p13.candidates.initialTitle"
        :description="zhCN.p13.candidates.initialHint"
        compact
      />
      <StateView
        v-else-if="!candidates.length"
        state="empty"
        :title="candidateEmptyCopy"
        :description="zhCN.p13.candidates.emptyHint"
        compact
      />
      <StateView
        v-else-if="!filteredCandidates.length"
        state="empty"
        :title="zhCN.p13.search.filteredEmpty"
        compact
      />
      <ElTable
        v-else
        :data="filteredCandidates"
        size="small"
        border
        row-key="offer_id"
        style="width: 100%"
        @row-click="selectCandidate"
      >
        <ElTableColumn :label="zhCN.p13.candidates.columns.rank" width="66" align="right">
          <template #default="{ row }">
            <span class="sp-mono">{{ row.rank }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.candidates.columns.offer" min-width="260">
          <template #default="{ row }">
            <div class="sp-p13__offer">
              <span class="sp-p13__offer-title" :title="row.title">{{ row.title }}</span>
              <span class="sp-p13__offer-meta">
                <span>{{ row.supplier || zhCN.common.none }}</span>
                <a
                  v-if="row.url"
                  :href="row.url"
                  class="sp-p13__offer-link"
                  target="_blank"
                  rel="noopener"
                  @click.stop
                >
                  {{ zhCN.p13.candidates.sourceLink }}
                </a>
              </span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.candidates.columns.price" width="128" align="right">
          <template #default="{ row }">
            <div class="sp-p13__price-cell">
              <span class="sp-mono sp-p13__price">¥{{ money(row.price) }}</span>
              <span class="sp-p13__post">{{ postFeeText(row.post_fee) }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.candidates.columns.moq" width="78" align="right">
          <template #default="{ row }">
            <span class="sp-mono">{{ row.moq }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.candidates.columns.sales" width="112" align="right">
          <template #default="{ row }">
            <span class="sp-mono">{{ formatNumber(amountOf(row.sales_30d)) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.candidates.columns.score" width="78" align="right">
          <template #default="{ row }">
            <span class="sp-mono">{{ amountOf(row.score).toFixed(2) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.candidates.columns.risk" min-width="170">
          <template #default="{ row }">
            <div v-if="riskFlags(row).length" class="sp-p13__risks">
              <span
                v-for="flag in riskFlags(row)"
                :key="flag"
                class="sp-chip sp-p13__risk"
                :class="{ 'sp-p13__risk--danger': isBrandRisk(flag) }"
                :title="isBrandRisk(flag) ? zhCN.p13.riskBrandHint : ''"
              >
                {{ riskLabel(flag) }}
              </span>
            </div>
            <span v-else class="sp-faint">{{ zhCN.p13.candidates.noRisk }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.candidates.columns.select" width="88" fixed="right">
          <template #default="{ row }">
            <button
              type="button"
              class="sp-link-btn sp-p13__select"
              :class="{ 'is-selected': row.offer_id === selectedOfferId }"
              :data-select-offer="row.offer_id"
              @click.stop="selectCandidate(row)"
            >
              {{
                row.offer_id === selectedOfferId
                  ? zhCN.p13.candidates.selected
                  : zhCN.p13.candidates.select
              }}
            </button>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>

    <section
      v-if="selectedCandidate"
      class="sp-panel sp-p13__purchase"
      data-p13="purchase-prepare"
    >
      <div class="sp-panel__header">
        <div class="sp-panel__title">{{ zhCN.p13.purchase.title }}</div>
        <span class="sp-panel__hint">{{ zhCN.p13.purchase.hint }}</span>
      </div>
      <div class="sp-p13__purchase-body">
        <div class="sp-p13__purchase-offer">
          <span class="sp-faint">{{ zhCN.p13.purchase.selectedOffer }}</span>
          <span class="sp-p13__purchase-title" :title="selectedCandidate.title">
            {{ selectedCandidate.title }}
          </span>
          <span class="sp-mono sp-faint">{{ selectedCandidate.offer_id }}</span>
        </div>
        <div v-if="canCreate" class="sp-p13__purchase-form">
          <label class="sp-p13__field">
            <span class="sp-p13__label">{{ zhCN.p13.purchase.quantity }}</span>
            <input
              v-model="quantity"
              class="sp-p13__control sp-p13__control--qty"
              type="number"
              step="1"
              :min="selectedCandidate.moq"
              data-field="purchase-quantity"
              :disabled="creating"
            />
            <span class="sp-p13__hint">
              {{ zhCN.p13.purchase.moqHint(amountOf(selectedCandidate.moq)) }}
            </span>
          </label>
          <div class="sp-p13__estimate">
            <span class="sp-faint">{{ zhCN.p13.purchase.estimate }}</span>
            <span class="sp-mono sp-p13__estimate-value">
              {{ estimateTotal ? `¥${estimateTotal}` : zhCN.common.none }}
            </span>
            <span class="sp-p13__hint">{{ zhCN.p13.purchase.estimateHint }}</span>
          </div>
          <ElButton
            size="small"
            type="primary"
            data-action="create-purchase-order"
            :loading="creating"
            @click="submitPurchase"
          >
            {{ creating ? zhCN.p13.purchase.creating : zhCN.p13.purchase.create }}
          </ElButton>
        </div>
        <div v-else class="sp-p13__hint" data-p13="purchase-viewer-hint">
          {{ isViewer ? zhCN.p13.purchase.viewerHint : zhCN.p13.readonlyHint }}
        </div>
      </div>
      <div v-if="createError" class="sp-p13__error" role="alert">{{ createError }}</div>
    </section>

    <section class="sp-panel sp-p13__orders" data-p13="purchase-orders">
      <div class="sp-panel__header">
        <div class="sp-panel__title">
          <span>{{ zhCN.p13.orders.title }}</span>
          <span v-if="orders.length" class="sp-panel__count">{{ orders.length }}</span>
        </div>
        <div class="sp-p13__orders-hint">
          <span>{{ zhCN.p13.orders.hint }}</span>
          <StatusBadge v-if="purchases?.readonly" :label="zhCN.common.readonly" tone="neutral" />
        </div>
      </div>
      <div v-if="refreshNote" class="sp-p13__note" role="note">
        <span class="sp-faint">{{ zhCN.p13.orders.noteLabel }}</span>
        <span>{{ refreshNote }}</span>
      </div>
      <StateView v-if="purchasesLoading" state="loading" compact />
      <StateView
        v-else-if="purchasesError"
        state="error"
        :title="zhCN.p13.orders.loadFailed"
        :description="purchasesError"
        compact
        @retry="loadPurchases"
      />
      <StateView
        v-else-if="!orders.length"
        state="empty"
        :title="purchaseEmptyCopy"
        :description="zhCN.p13.orders.emptyHint"
        compact
      />
      <ElTable v-else :data="orders" size="small" border row-key="plan_id" style="width: 100%">
        <ElTableColumn :label="zhCN.p13.orders.columns.plan" min-width="128">
          <template #default="{ row }">
            <span class="sp-mono sp-p13__plan" :title="row.plan_id">
              {{ truncateHead(row.plan_id, 14) }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.orders.columns.items" min-width="128">
          <template #default="{ row }">
            <span class="sp-p13__items">
              {{ zhCN.p13.orders.itemsSummary(row.items.length, row.quantity) }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.orders.columns.total" width="116" align="right">
          <template #default="{ row }">
            <span class="sp-mono">¥{{ money(row.total) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.orders.columns.status" width="104">
          <template #default="{ row }">
            <StatusBadge
              :label="purchaseStatusLabel(row)"
              :tone="purchaseStatusTone(row.status)"
            />
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.orders.columns.createdAt" width="152">
          <template #default="{ row }">
            <span class="sp-mono sp-p13__time">
              {{ formatDateTime(row.created_at) || zhCN.common.none }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p13.orders.columns.actions" width="248" fixed="right">
          <template #default="{ row }">
            <div class="sp-p13__order-actions">
              <a
                v-if="row.continue_url && isAwaiting(row.status)"
                :href="row.continue_url"
                class="sp-p13__continue"
                data-p13="purchase-continue"
                target="_blank"
                rel="noopener"
              >
                {{ zhCN.p13.orders.continue }}
              </a>
              <ElButton
                size="small"
                data-action="refresh-purchase"
                :data-plan-id="row.plan_id"
                :loading="refreshingPlanId === row.plan_id"
                @click.stop="refreshOrder(row)"
              >
                {{ zhCN.p13.orders.refresh }}
              </ElButton>
            </div>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p13__meta {
  margin-left: 5px;
  color: var(--sp-text);
}

.sp-p13__provider {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 9px 12px;
  border: 1px solid var(--sp-border);
  border-left: 3px solid var(--sp-primary);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
}

.sp-p13__provider-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.sp-p13__provider-title {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-p13__provider-body {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 16px;
  font-size: 11.5px;
}

.sp-p13__provider-item {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  color: var(--sp-text);
}

.sp-p13__provider-note {
  flex: 1 1 320px;
  min-width: 0;
  font-size: 11px;
  color: var(--sp-muted);
}

.sp-p13__boundary {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 7px 12px;
  border: 1px solid var(--sp-info-border);
  border-left: 3px solid var(--sp-info);
  border-radius: var(--sp-radius);
  background: var(--sp-info-soft);
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--sp-text);
}

.sp-p13__boundary-label {
  flex: none;
  font-weight: 600;
  color: var(--sp-info);
}

.sp-p13__search-body {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 11px 14px 8px;
}

.sp-p13__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.sp-p13__field--grow {
  flex: 1;
}

.sp-p13__label {
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-p13__control {
  height: 28px;
  padding: 0 9px;
  border: 1px solid var(--sp-border-strong);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  font-size: 12px;
  color: var(--sp-text);
}

.sp-p13__control:focus {
  border-color: var(--sp-primary);
  outline: none;
}

.sp-p13__control--price {
  width: 88px;
}

.sp-p13__control--qty {
  width: 120px;
}

.sp-p13__filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 14px;
  padding: 0 14px 11px;
  font-size: 11.5px;
}

.sp-p13__filters-title {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-p13__check {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--sp-text);
}

.sp-p13__price {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.sp-p13__filters-hint {
  flex: 1 1 240px;
  min-width: 0;
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-p13__candidates {
  overflow: hidden;
}

.sp-p13__offer {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.sp-p13__offer-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-p13__offer-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-p13__offer-link {
  font-size: 10.5px;
}

.sp-p13__price-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
}

.sp-p13__price {
  color: var(--sp-text);
}

.sp-p13__post {
  font-size: 10px;
  color: var(--sp-faint);
}

.sp-p13__risks {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.sp-p13__risk {
  font-size: 10px;
}

.sp-p13__risk--danger {
  border-color: var(--sp-danger-border);
  background: var(--sp-danger-soft);
  color: var(--sp-danger);
  font-weight: 600;
}

.sp-p13__select.is-selected {
  color: var(--sp-primary);
  font-weight: 600;
}

.sp-p13__purchase-body {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px 20px;
  padding: 11px 14px 13px;
}

.sp-p13__purchase-offer {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px 10px;
  min-width: 0;
  font-size: 11.5px;
}

.sp-p13__purchase-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-p13__purchase-form {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 14px;
}

.sp-p13__hint {
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-p13__estimate {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11px;
}

.sp-p13__estimate-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-p13__orders-hint {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-p13__note {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 7px 14px;
  border-top: 1px dashed var(--sp-border);
  background: var(--sp-surface-sunken);
  font-size: 11px;
  color: var(--sp-muted);
}

.sp-p13__plan {
  color: var(--sp-text);
}

.sp-p13__items {
  font-size: 11px;
  color: var(--sp-muted);
}

.sp-p13__time {
  font-size: 10.5px;
  color: var(--sp-muted);
  white-space: nowrap;
}

.sp-p13__order-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.sp-p13__continue {
  font-size: 11.5px;
  white-space: nowrap;
}

.sp-p13__error {
  margin: 0 14px 11px;
  padding: 6px 10px;
  border: 1px solid var(--sp-danger-border);
  border-radius: var(--sp-radius);
  background: var(--sp-danger-soft);
  font-size: 11.5px;
  color: var(--sp-danger);
}

@media (max-width: 860px) {
  .sp-p13__search-body {
    flex-direction: column;
    align-items: stretch;
  }
  .sp-p13__provider-note {
    flex-basis: 100%;
  }
  .sp-p13__purchase-title {
    max-width: 100%;
  }
}
</style>
