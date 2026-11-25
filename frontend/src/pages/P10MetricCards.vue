<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElButton, ElTable, ElTableColumn } from 'element-plus'

import {
  ApiError,
  fetchMetricCard,
  fetchMetricCards,
  fetchMetricDiff,
  releaseMetricCard,
} from '../api/client'
import type {
  MetricCardListItem,
  MetricCardPayload,
  MetricCardsResponse,
  MetricDiffResponse,
  MetricReleaseSummary,
  ReleaseCheck,
} from '../api/types'
import { RELEASE_FAILED_COPY, zhCN, type Tone } from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useContextStore } from '../stores/context'
import { useToast } from '../composables/useToast'
import { formatDate, formatDateTime, prettyJson } from '../utils/format'
import DrawerPanel from '../components/DrawerPanel.vue'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

const session = useSessionStore()
const context = useContextStore()
const { push } = useToast()

const payload = ref<MetricCardsResponse | null>(null)
const loading = ref(true)
const errorText = ref('')

const drawerOpen = ref(false)
const detailTarget = ref<MetricCardListItem | null>(null)
const detail = ref<MetricCardPayload | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

const diff = ref<MetricDiffResponse | null>(null)
const diffLoading = ref(false)
const diffError = ref('')

const releaseOpen = ref(false)
const releasePanelRef = ref<HTMLElement | null>(null)
const releaseTarget = ref<MetricCardListItem | null>(null)
const releaseLoading = ref('')
const releaseResult = ref<MetricReleaseSummary | null>(null)
const releaseError = ref('')
const releaseFailed = ref(false)
let requestSeq = 0
let detailSeq = 0
let diffSeq = 0

const role = computed(() => session.role || context.role)
const canRelease = computed(() => role.value === 'OWNER')
const rows = computed(() => payload.value?.items ?? [])
const emptyCopy = computed(() => payload.value?.empty_copy || zhCN.p10.empty)

const detailRows = computed(() => {
  const card = detail.value
  if (!card) return []
  return [
    { label: zhCN.drill.definition, value: card.business_question || card.name, mono: false },
    { label: zhCN.drill.formula, value: card.compute.formula || zhCN.p10.detail.empty, mono: true },
    {
      label: zhCN.drill.denominator,
      value: card.compute.denominator || zhCN.p10.detail.empty,
      mono: true,
    },
    { label: zhCN.drill.unit, value: card.compute.unit || zhCN.p10.detail.empty, mono: false },
    { label: zhCN.drill.precision, value: String(card.compute.precision), mono: true },
    { label: zhCN.drill.additivity, value: additivityLabel(card.compute.additivity), mono: false },
    { label: zhCN.drill.nullPolicy, value: nullPolicyLabel(card.compute.null_policy), mono: false },
    {
      label: zhCN.drill.sourceMapping,
      value: card.compute.source_mapping || zhCN.p10.detail.empty,
      mono: true,
    },
  ]
})

const releaseChecks = computed<ReleaseCheck[]>(() => releaseResult.value?.checks ?? [])

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof ApiError) return cause.userMessage || fallback
  if (cause && typeof cause === 'object' && 'userMessage' in cause) {
    return String((cause as { userMessage: unknown }).userMessage) || fallback
  }
  return fallback
}

function additivityLabel(value: string): string {
  return zhCN.drill.additivityLabels[value] ?? value
}

function nullPolicyLabel(value: string): string {
  return zhCN.drill.nullPolicyLabels[value] ?? value
}

function checkName(name: string): string {
  return zhCN.p10.release.checkNames[name] ?? name
}

function releaseState(row: unknown): { label: string; tone: Tone; at: string } {
  const release = (row as MetricCardListItem).release
  if (!release) {
    return { label: zhCN.p10.releaseState.never, tone: 'neutral', at: '' }
  }
  return {
    label: release.gate_passed ? zhCN.p10.releaseState.passed : zhCN.p10.releaseState.failed,
    tone: release.gate_passed ? 'success' : 'danger',
    at: formatDateTime(release.checked_at) || '',
  }
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return zhCN.common.none
  if (typeof value === 'object') return prettyJson(value)
  return String(value)
}

function readReleaseChecks(details: Record<string, unknown>): ReleaseCheck[] {
  const raw = details.release
  if (!raw || typeof raw !== 'object') return []
  const checks = (raw as { checks?: unknown }).checks
  if (!Array.isArray(checks)) return []
  return checks.filter((item): item is ReleaseCheck => {
    if (!item || typeof item !== 'object') return false
    const candidate = item as Record<string, unknown>
    return typeof candidate.name === 'string' && typeof candidate.passed === 'boolean'
  })
}

function readRelease(details: Record<string, unknown>): MetricReleaseSummary | null {
  const raw = details.release
  if (!raw || typeof raw !== 'object') return null
  const value = raw as Record<string, unknown>
  const checks = readReleaseChecks(details)
  if (!checks.length) return null
  return {
    metric_code: typeof value.metric_code === 'string' ? value.metric_code : '',
    version: typeof value.version === 'string' ? value.version : '',
    gate_passed: Boolean(value.gate_passed),
    checks,
    checked_by: typeof value.checked_by === 'string' ? value.checked_by : null,
    checked_at: typeof value.checked_at === 'string' ? value.checked_at : null,
  }
}

async function load(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  errorText.value = ''
  try {
    const response = await fetchMetricCards()
    if (seq !== requestSeq) return
    payload.value = response
  } catch (cause) {
    if (seq !== requestSeq) return
    errorText.value = errorMessage(cause, zhCN.p10.loadFailed)
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

async function loadDetail(metricCode: string, seq: number): Promise<void> {
  try {
    const response = await fetchMetricCard(metricCode)
    if (seq !== detailSeq) return
    detail.value = response
  } catch (cause) {
    if (seq !== detailSeq) return
    detailError.value = errorMessage(cause, zhCN.p10.detail.loadFailed)
  } finally {
    if (seq === detailSeq) detailLoading.value = false
  }
}

async function loadDiff(metricCode: string, seq: number): Promise<void> {
  try {
    const response = await fetchMetricDiff(metricCode)
    if (seq !== diffSeq) return
    diff.value = response
  } catch (cause) {
    if (seq !== diffSeq) return
    diffError.value = errorMessage(cause, zhCN.p10.diff.loadFailed)
  } finally {
    if (seq === diffSeq) diffLoading.value = false
  }
}

function openDetail(row: unknown): void {
  const item = row as MetricCardListItem
  detailTarget.value = item
  detail.value = null
  detailError.value = ''
  detailLoading.value = true
  diff.value = null
  diffError.value = ''
  diffLoading.value = true
  drawerOpen.value = true
  const detailToken = ++detailSeq
  const diffToken = ++diffSeq
  void loadDetail(item.metric_code, detailToken)
  void loadDiff(item.metric_code, diffToken)
}

function closeDetail(): void {
  drawerOpen.value = false
  detailTarget.value = null
  detail.value = null
  diff.value = null
}

async function runRelease(row: unknown): Promise<void> {
  const target = row as MetricCardListItem
  releaseTarget.value = target
  releaseResult.value = null
  releaseError.value = ''
  releaseFailed.value = false
  releaseOpen.value = true
  releaseLoading.value = target.metric_code
  await nextTick()
  releasePanelRef.value?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
  try {
    const result = await releaseMetricCard(target.metric_code)
    releaseResult.value = result
    if (!result.gate_passed) {
      releaseFailed.value = true
      releaseError.value = zhCN.p10.release.failed
    } else {
      push(zhCN.p10.releaseDone, 'success')
    }
    await load()
  } catch (cause) {
    if (cause instanceof ApiError) {
      const result = readRelease(cause.details)
      if (result) releaseResult.value = result
      if (cause.status === 409 || cause.code === 'E007') {
        releaseFailed.value = true
        releaseError.value = releaseResult.value?.gate_passed
          ? zhCN.p10.release.failedGeneric
          : zhCN.p10.release.failed
      } else {
        releaseError.value = cause.userMessage || zhCN.p10.release.failedGeneric
      }
    } else {
      releaseError.value = errorMessage(cause, zhCN.p10.release.failedGeneric)
    }
    if (releaseFailed.value) push(RELEASE_FAILED_COPY, 'danger')
    else push(releaseError.value, 'danger')
    await load()
  } finally {
    releaseLoading.value = ''
  }
}

function closeRelease(): void {
  releaseOpen.value = false
  releaseTarget.value = null
  releaseResult.value = null
  releaseError.value = ''
  releaseFailed.value = false
}

function inspectedText(): string {
  const inspected = detail.value?.evidence.last_inspected_value
  if (!inspected) return zhCN.drill.inspectedEmpty
  return `${inspected.value ?? zhCN.p10.detail.empty} · ${formatDate(inspected.stat_date) || zhCN.p10.detail.empty}`
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="sp-page sp-p10">
    <PageHeader
      :eyebrow="zhCN.p10.eyebrow"
      :title="zhCN.p10.title"
      :description="zhCN.p10.description"
    >
      <template #meta>
        <StatusBadge
          v-if="!canRelease"
          :label="zhCN.p10.readonlyHint"
          tone="neutral"
        />
      </template>
      <template #actions>
        <ElButton size="small" :loading="loading" @click="load">{{ zhCN.p10.refresh }}</ElButton>
      </template>
    </PageHeader>

    <div class="sp-p10__contract" role="note">{{ zhCN.p10.contractNote }}</div>

    <section class="sp-panel sp-p10__table-panel">
      <div class="sp-panel__header">
        <div class="sp-panel__title">
          <span>{{ zhCN.p10.tableTitle }}</span>
          <span v-if="rows.length" class="sp-panel__count">{{ rows.length }}</span>
        </div>
        <span class="sp-panel__hint">{{ zhCN.p10.tableHint }}</span>
      </div>

      <StateView v-if="loading" state="loading" compact />
      <StateView
        v-else-if="errorText"
        state="error"
        :title="zhCN.p10.loadFailed"
        :description="errorText"
        compact
        @retry="load"
      />
      <StateView
        v-else-if="!rows.length"
        state="empty"
        :title="emptyCopy"
        :description="zhCN.p10.emptyHint"
        compact
      />
      <ElTable v-else :data="rows" size="small" border style="width: 100%" @row-click="openDetail">
        <ElTableColumn prop="metric_code" :label="zhCN.p10.columns.code" width="116">
          <template #default="{ row }">
            <span class="sp-mono sp-p10__code">{{ row.metric_code }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="display_name" :label="zhCN.p10.columns.name" min-width="130" />
        <ElTableColumn prop="version" :label="zhCN.p10.columns.version" width="74">
          <template #default="{ row }">
            <span class="sp-mono">{{ row.version }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="unit" :label="zhCN.p10.columns.unit" width="66" />
        <ElTableColumn :label="zhCN.p10.columns.additivity" width="118">
          <template #default="{ row }">
            <span class="sp-chip">{{ additivityLabel(row.additivity) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p10.columns.source" min-width="170">
          <template #default="{ row }">
            <span class="sp-mono sp-p10__source" :title="row.source_mapping">
              {{ row.source_mapping || zhCN.common.none }}
            </span>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p10.columns.release" width="150">
          <template #default="{ row }">
            <div class="sp-p10__release">
              <StatusBadge :label="releaseState(row).label" :tone="releaseState(row).tone" />
              <span v-if="releaseState(row).at" class="sp-p10__release-at sp-mono">
                {{ releaseState(row).at }}
              </span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn :label="zhCN.p10.columns.actions" width="132" fixed="right">
          <template #default="{ row }">
            <ElButton
              v-if="canRelease"
              size="small"
              :loading="releaseLoading === row.metric_code"
              :disabled="Boolean(releaseLoading) && releaseLoading !== row.metric_code"
              @click.stop="runRelease(row)"
            >
              {{ releaseLoading === row.metric_code ? zhCN.p10.releaseRunning : zhCN.p10.runCheck }}
            </ElButton>
            <span v-else class="sp-faint">{{ zhCN.common.readonly }}</span>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>

    <DrawerPanel
      :open="drawerOpen"
      :title="zhCN.p10.detail.title"
      :subtitle="detailTarget ? `${detailTarget.metric_code} @ ${detailTarget.version}` : zhCN.p10.detail.subtitle"
      width="620px"
      :close-label="zhCN.p10.detail.close"
      @close="closeDetail"
    >
      <StateView v-if="detailLoading" state="loading" compact />
      <StateView
        v-else-if="detailError"
        state="error"
        :title="zhCN.p10.detail.loadFailed"
        :description="detailError"
        compact
      />
      <div v-else-if="detail" class="sp-p10__detail">
        <div class="sp-p10__detail-head">
          <span class="sp-p10__detail-name">{{ detail.display_name }}</span>
          <span class="sp-chip sp-mono">{{ detail.metric_code }} @ {{ detail.version }}</span>
          <StatusBadge :status="detail.status" />
        </div>

        <dl class="sp-p10__kv">
          <template v-for="field in detailRows" :key="field.label">
            <dt>{{ field.label }}</dt>
            <dd :class="{ 'sp-mono': field.mono }">{{ field.value }}</dd>
          </template>
        </dl>

        <section class="sp-p10__sub">
          <h3>{{ zhCN.drill.probeSql }}</h3>
          <pre class="sp-p10__sql">{{ detail.evidence.probe_sql_template || zhCN.p10.detail.empty }}</pre>
        </section>

        <section class="sp-p10__sub">
          <h3>{{ zhCN.drill.qualityTests }}</h3>
          <ul v-if="detail.quality.quality_tests.length" class="sp-p10__checks">
            <li v-for="(item, index) in detail.quality.quality_tests" :key="index" class="sp-p10__check">
              <span class="sp-chip">{{ index + 1 }}</span>
              <span>{{ item }}</span>
            </li>
          </ul>
          <p v-else class="sp-faint">{{ zhCN.p10.detail.noQuality }}</p>
        </section>

        <section class="sp-p10__sub">
          <h3>{{ zhCN.p10.detail.evidence }}</h3>
          <dl class="sp-p10__kv">
            <dt>{{ zhCN.drill.inspectedValue }}</dt>
            <dd>{{ inspectedText() }}</dd>
            <dt>{{ zhCN.drill.runLink }}</dt>
            <dd class="sp-mono">{{ detail.evidence.run_id || zhCN.common.none }}</dd>
            <dt>{{ zhCN.drill.odsRefs }}</dt>
            <dd>
              <div v-if="detail.evidence.ods_refs.length" class="sp-p10__refs">
                <span
                  v-for="ref in detail.evidence.ods_refs"
                  :key="ref"
                  class="sp-chip sp-mono"
                  :title="ref"
                >
                  {{ ref }}
                </span>
              </div>
              <span v-else class="sp-faint">{{ zhCN.p10.detail.noOds }}</span>
            </dd>
          </dl>
        </section>

        <section class="sp-p10__sub">
          <h3>{{ zhCN.p10.diff.title }}</h3>
          <StateView v-if="diffLoading" state="loading" compact />
          <p v-else-if="diffError" class="sp-p10__error">{{ diffError }}</p>
          <template v-else-if="diff">
            <div v-if="diff.from || diff.to" class="sp-p10__diff-meta sp-mono">
              <span>{{ zhCN.p10.diff.from }} {{ diff.from || zhCN.common.none }}</span>
              <span class="sp-faint">→</span>
              <span>{{ zhCN.p10.diff.to }} {{ diff.to || zhCN.common.none }}</span>
            </div>
            <table v-if="diff.diffs.length" class="sp-p10__diff-table">
              <thead>
                <tr>
                  <th>{{ zhCN.p10.diff.field }}</th>
                  <th>{{ zhCN.p10.diff.before }}</th>
                  <th>{{ zhCN.p10.diff.after }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="entry in diff.diffs" :key="entry.field">
                  <td class="sp-mono">{{ entry.field }}</td>
                  <td>{{ displayValue(entry.before) }}</td>
                  <td>{{ displayValue(entry.after) }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else class="sp-p10__diff-empty">
              {{ diff.note || zhCN.p10.diff.empty }}
            </p>
          </template>
        </section>
      </div>
    </DrawerPanel>

    <section v-if="releaseOpen" ref="releasePanelRef" class="sp-panel sp-p10__release-panel">
      <div class="sp-panel__header">
        <div class="sp-panel__title">
          <span>{{ zhCN.p10.release.title }}</span>
          <span v-if="releaseTarget" class="sp-mono sp-faint">
            {{ releaseTarget.metric_code }} @ {{ releaseTarget.version }}
          </span>
        </div>
        <ElButton size="small" @click="closeRelease">{{ zhCN.p10.release.close }}</ElButton>
      </div>
      <div class="sp-p10__release-body">
        <StateView v-if="releaseLoading" state="loading" compact />
        <div v-else class="sp-p10__release-result">
          <div
            v-if="releaseError"
            class="sp-p10__release-banner"
            :class="releaseFailed ? 'is-failed' : 'is-error'"
            role="alert"
          >
            {{ releaseError }}
          </div>
          <div
            v-else-if="releaseResult?.gate_passed"
            class="sp-p10__release-banner is-passed"
            role="status"
          >
            {{ zhCN.p10.release.success }}
          </div>

          <div v-if="releaseResult" class="sp-p10__release-meta">
            <span class="sp-mono">{{ releaseResult.metric_code }} @ {{ releaseResult.version }}</span>
            <span v-if="releaseResult.checked_by">
              {{ zhCN.p10.release.checkedBy }} · {{ releaseResult.checked_by }}
            </span>
            <span v-if="releaseResult.checked_at">
              {{ zhCN.p10.release.checkedAt }} · {{ formatDateTime(releaseResult.checked_at) }}
            </span>
          </div>

          <div class="sp-p10__checks-head">{{ zhCN.p10.release.checksTitle }}</div>
          <ul v-if="releaseChecks.length" class="sp-p10__checks">
            <li
              v-for="check in releaseChecks"
              :key="check.name"
              class="sp-p10__check"
              :class="check.passed ? 'is-passed' : 'is-failed'"
            >
              <div class="sp-p10__check-head">
                <span class="sp-p10__check-name">{{ checkName(check.name) }}</span>
                <span class="sp-mono sp-faint">{{ check.name }}</span>
                <StatusBadge
                  :label="check.passed ? zhCN.p10.release.passed : zhCN.p10.release.failedCheck"
                  :tone="check.passed ? 'success' : 'danger'"
                />
              </div>
              <p class="sp-p10__check-detail">{{ check.detail || zhCN.common.none }}</p>
            </li>
          </ul>
          <p v-else class="sp-faint">{{ zhCN.p10.release.noChecks }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p10__contract {
  padding: 6px 11px;
  border: 1px solid var(--sp-primary-soft-strong);
  border-left: 3px solid var(--sp-primary);
  border-radius: var(--sp-radius);
  background: var(--sp-primary-soft);
  color: var(--sp-primary);
  font-size: 11.5px;
}

.sp-p10__table-panel {
  overflow: hidden;
}

.sp-p10__release-panel {
  overflow: hidden;
}

.sp-p10__release-body {
  padding: 12px;
}

.sp-p10__table-panel :deep(.el-table__row) {
  cursor: pointer;
}

.sp-p10__code {
  font-weight: 600;
  color: var(--sp-text);
}

.sp-p10__source {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--sp-muted);
}

.sp-p10__release {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.sp-p10__release-at {
  font-size: 9.5px;
  color: var(--sp-faint);
}

.sp-p10__detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p10__detail-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.sp-p10__detail-name {
  font-size: 14px;
  font-weight: 650;
  color: var(--sp-text);
}

.sp-p10__kv {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 5px 10px;
  margin: 0;
  padding: 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 12px;
}

.sp-p10__kv dt {
  color: var(--sp-muted);
}

.sp-p10__kv dd {
  margin: 0;
  min-width: 0;
  color: var(--sp-text);
  word-break: break-word;
}

.sp-p10__sub h3 {
  margin-bottom: 5px;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-p10__sql {
  max-height: 180px;
  margin: 0;
  padding: 9px 10px;
  overflow: auto;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 11px;
  line-height: 1.55;
  color: var(--sp-text);
  white-space: pre-wrap;
  word-break: break-word;
}

.sp-p10__checks {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sp-p10__check {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 7px 9px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface);
}

.sp-p10__check.is-passed {
  border-left: 3px solid var(--sp-success);
}

.sp-p10__check.is-failed {
  border-left: 3px solid var(--sp-danger);
  background: var(--sp-danger-soft);
}

.sp-p10__check-head {
  display: flex;
  align-items: center;
  gap: 7px;
}

.sp-p10__check-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-p10__check-detail {
  font-size: 11px;
  line-height: 1.5;
  color: var(--sp-muted);
  word-break: break-word;
}

.sp-p10__refs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.sp-p10__diff-meta {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-p10__diff-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

.sp-p10__diff-table th,
.sp-p10__diff-table td {
  padding: 4px 8px;
  border: 1px solid var(--sp-border);
  text-align: left;
  vertical-align: top;
  word-break: break-word;
}

.sp-p10__diff-table th {
  background: var(--sp-surface-sunken);
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-p10__diff-empty {
  font-size: 12px;
  color: var(--sp-muted);
}

.sp-p10__error {
  font-size: 12px;
  color: var(--sp-danger);
}

.sp-p10__release-result {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sp-p10__release-banner {
  padding: 8px 11px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  font-size: 12px;
  font-weight: 600;
}

.sp-p10__release-banner.is-passed {
  border-color: var(--sp-success-border);
  background: var(--sp-success-soft);
  color: var(--sp-success);
}

.sp-p10__release-banner.is-failed,
.sp-p10__release-banner.is-error {
  border-color: var(--sp-danger-border);
  background: var(--sp-danger-soft);
  color: var(--sp-danger);
}

.sp-p10__release-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-p10__checks-head {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--sp-muted);
}
</style>
