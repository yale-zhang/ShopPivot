<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton } from 'element-plus'

import {
  ApiError,
  approveWritePlan,
  compensateWritePlan,
  fetchChangeOrder,
  rejectWritePlan,
  transferChangeOrder,
  withdrawWritePlan,
} from '../api/client'
import type { ChangeOrderPayload } from '../api/types'
import { READONLY_COPY, zhCN } from '../i18n/zh-CN'
import { useContextStore } from '../stores/context'
import { useSessionStore } from '../stores/session'
import { formatDateTime, truncateHead } from '../utils/format'
import { labelForStatus, toneForStatus } from '../utils/status'
import { useToast } from '../composables/useToast'
import ActionDialog from '../components/ActionDialog.vue'
import ApprovalActions from '../components/ApprovalActions.vue'
import BeforeAfterTable from '../components/BeforeAfterTable.vue'
import EvidencePack from '../components/EvidencePack.vue'
import ExecutionPanel from '../components/ExecutionPanel.vue'
import PageHeader from '../components/PageHeader.vue'
import ResultTimeline from '../components/ResultTimeline.vue'
import RollbackPanel from '../components/RollbackPanel.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'
import TransferDialog from '../components/TransferDialog.vue'

type ActionMode = 'approve' | 'reject' | 'withdraw' | 'compensate'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const context = useContextStore()
const { push } = useToast()

const order = ref<ChangeOrderPayload | null>(null)
const loading = ref(true)
const errorText = ref('')
const notFound = ref(false)
const dialogOpen = ref(false)
const dialogMode = ref<ActionMode>('approve')
const dialogError = ref('')
const actionPending = ref(false)
const transferOpen = ref(false)
const transferError = ref('')
const transferPending = ref(false)
let requestSeq = 0

const orderNo = computed(() => {
  const id = route.params.id
  return typeof id === 'string' ? id : ''
})

const readonlyCopy = computed(() => order.value?.readonly_copy || READONLY_COPY)
const hashDisplay = computed(() => truncateHead(order.value?.header.write_plan_hash ?? '', 16))

const planId = computed(() => order.value?.plan_id ?? '')
const planStatus = computed(() => order.value?.plan_status ?? '')
const execution = computed(() => order.value?.execution ?? null)
const role = computed(() => session.role || context.role)

const hasPlan = computed(() => Boolean(planId.value))
const canApprove = computed(() => Boolean(order.value?.can_approve) && hasPlan.value)
const readonlyView = computed(
  () => Boolean(order.value?.readonly) || !Boolean(order.value?.can_approve),
)
const withdrawable = computed(
  () => hasPlan.value && planStatus.value === 'APPROVED' && !execution.value,
)
const compensatable = computed(
  () => hasPlan.value && planStatus.value === 'VERIFIED' && role.value === 'OWNER',
)
const transferable = computed(
  () => canApprove.value && (order.value?.status ?? '') === 'PENDING',
)

interface DialogConfig {
  title: string
  description: string
  fieldLabel: string
  placeholder: string
  confirmLabel: string
  required: boolean
}

const dialogConfig = computed<DialogConfig>(() => {
  if (dialogMode.value === 'approve') {
    return {
      title: zhCN.p06.actions.approveTitle,
      description: zhCN.p06.actions.approveConfirmBody,
      fieldLabel: zhCN.p06.actions.approveReasonLabel,
      placeholder: zhCN.p06.actions.reasonPlaceholder,
      confirmLabel: zhCN.p06.actions.approveConfirm,
      required: false,
    }
  }
  if (dialogMode.value === 'reject') {
    return {
      title: zhCN.p06.actions.rejectTitle,
      description: zhCN.p06.actions.rejectBody,
      fieldLabel: zhCN.p06.actions.rejectReasonLabel,
      placeholder: zhCN.p06.actions.reasonPlaceholder,
      confirmLabel: zhCN.p06.actions.rejectConfirm,
      required: true,
    }
  }
  if (dialogMode.value === 'withdraw') {
    return {
      title: zhCN.p06.actions.withdrawTitle,
      description: zhCN.p06.actions.withdrawBody,
      fieldLabel: zhCN.p06.actions.withdrawReasonLabel,
      placeholder: zhCN.p06.actions.reasonPlaceholder,
      confirmLabel: zhCN.p06.actions.withdrawConfirm,
      required: false,
    }
  }
  return {
    title: zhCN.p06.actions.compensateTitle,
    description: zhCN.p06.actions.compensateBody,
    fieldLabel: zhCN.p06.actions.compensateReasonLabel,
    placeholder: zhCN.p06.actions.reasonPlaceholder,
    confirmLabel: zhCN.p06.actions.compensateConfirm,
    required: true,
  }
})

const successCopy = computed(() => {
  if (dialogMode.value === 'approve') return zhCN.p06.actions.approveSuccess
  if (dialogMode.value === 'reject') return zhCN.p06.actions.rejectSuccess
  if (dialogMode.value === 'withdraw') return zhCN.p06.actions.withdrawSuccess
  return zhCN.p06.actions.compensateSuccess
})

const summaryFields = computed<Array<{ label: string; value: string; mono?: boolean }>>(() => {
  if (!order.value) return []
  const header = order.value.header
  return [
    { label: zhCN.p06.summary.taskId, value: order.value.task_id, mono: true },
    { label: zhCN.p06.summary.metricVersion, value: header.metric_version || zhCN.common.none, mono: true },
    { label: zhCN.p06.summary.snapshotTime, value: formatDateTime(header.snapshot_time) || zhCN.common.none },
    { label: zhCN.p06.summary.requestedBy, value: header.requested_by || zhCN.common.none },
    { label: zhCN.p06.summary.approver, value: header.approver || zhCN.common.none },
    { label: zhCN.p06.summary.scene, value: header.scene || zhCN.common.none, mono: true },
    { label: zhCN.p06.summary.platform, value: `${header.platform} / ${header.shop_id}`, mono: true },
    { label: zhCN.p06.summary.slaExpiresAt, value: formatDateTime(header.sla_expires_at) || zhCN.common.none },
    { label: zhCN.p06.summary.schemaVersion, value: header.schema_version || zhCN.common.none, mono: true },
  ]
})

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

async function load(): Promise<void> {
  const id = orderNo.value
  if (!id) {
    loading.value = false
    notFound.value = true
    order.value = null
    return
  }
  const seq = ++requestSeq
  loading.value = true
  errorText.value = ''
  notFound.value = false
  order.value = null
  try {
    const payload = await fetchChangeOrder(id)
    if (seq !== requestSeq) return
    order.value = payload
  } catch (cause) {
    if (seq !== requestSeq) return
    if (cause instanceof ApiError && cause.code === 'E008') {
      notFound.value = true
      return
    }
    errorText.value = errorMessage(cause, zhCN.p06.loadFailed)
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function backToTodos(): void {
  void router.push('/p05')
}

function openAction(mode: ActionMode): void {
  if (!hasPlan.value) {
    push(zhCN.p06.actions.missingPlan, 'warning')
    return
  }
  if ((mode === 'approve' || mode === 'reject') && !canApprove.value) return
  if (mode === 'withdraw' && !withdrawable.value) return
  if (mode === 'compensate' && !compensatable.value) return
  dialogError.value = ''
  dialogMode.value = mode
  dialogOpen.value = true
}

function closeAction(): void {
  if (actionPending.value) return
  dialogOpen.value = false
  dialogError.value = ''
}

function openTransfer(): void {
  if (!transferable.value) return
  transferError.value = ''
  transferOpen.value = true
}

function closeTransfer(): void {
  if (transferPending.value) return
  transferOpen.value = false
  transferError.value = ''
}

async function submitTransfer(payload: { approver: string; reason: string }): Promise<void> {
  const taskId = order.value?.task_id ?? ''
  if (!taskId) {
    transferError.value = zhCN.p06.actions.transferFailed
    return
  }
  transferPending.value = true
  transferError.value = ''
  try {
    await transferChangeOrder(taskId, payload.approver, payload.reason)
    push(zhCN.p06.actions.transferSuccess, 'success')
    transferOpen.value = false
    await load()
  } catch (cause) {
    transferError.value = errorMessage(cause, zhCN.p06.actions.transferFailed)
    push(transferError.value, 'danger')
  } finally {
    transferPending.value = false
  }
}

async function submitAction(reason: string): Promise<void> {
  const id = planId.value
  if (!id) {
    dialogError.value = zhCN.p06.actions.missingPlan
    return
  }
  actionPending.value = true
  dialogError.value = ''
  try {
    if (dialogMode.value === 'approve') await approveWritePlan(id, reason)
    else if (dialogMode.value === 'reject') await rejectWritePlan(id, reason)
    else if (dialogMode.value === 'withdraw') await withdrawWritePlan(id, reason)
    else await compensateWritePlan(id, reason)
    push(successCopy.value, 'success')
    dialogOpen.value = false
    await load()
  } catch (cause) {
    dialogError.value = errorMessage(cause, zhCN.p06.actions.actionFailed)
    push(dialogError.value, 'danger')
  } finally {
    actionPending.value = false
  }
}

watch(orderNo, () => {
  void load()
}, { immediate: true })
</script>

<template>
  <div class="sp-page sp-p06">
    <PageHeader
      :eyebrow="zhCN.p06.eyebrow"
      :title="zhCN.p06.title"
      :description="zhCN.p06.description"
    >
      <template #actions>
        <ElButton size="small" @click="backToTodos">{{ zhCN.p06.backTodos }}</ElButton>
      </template>
    </PageHeader>

    <StateView v-if="loading" state="loading" compact />
    <StateView
      v-else-if="errorText"
      state="error"
      :title="zhCN.p06.loadFailed"
      :description="errorText"
      compact
      @retry="load"
    />
    <StateView
      v-else-if="notFound || !order"
      state="empty"
      :title="zhCN.p06.empty"
      :description="zhCN.p06.emptyHint"
    >
      <ElButton size="small" @click="backToTodos">{{ zhCN.p06.backTodos }}</ElButton>
    </StateView>

    <template v-else>
      <section class="sp-panel sp-p06__summary">
        <div class="sp-panel__header">
          <div class="sp-panel__title">{{ zhCN.p06.summaryTitle }}</div>
          <StatusBadge :label="labelForStatus(order.status)" :tone="toneForStatus(order.status)" dot />
        </div>
        <div class="sp-p06__summary-body">
          <div class="sp-p06__summary-top">
            <span class="sp-p06__order-no sp-mono">{{ order.change_order_no }}</span>
            <span class="sp-chip">{{ zhCN.p06.summary.gateLevel }} · {{ order.header.gate_level }}</span>
            <span class="sp-p06__hash sp-mono" :title="order.header.write_plan_hash">
              {{ zhCN.p06.summary.writePlanHash }} · {{ hashDisplay }}
            </span>
          </div>
          <dl class="sp-p06__summary-grid">
            <template v-for="field in summaryFields" :key="field.label">
              <dt>{{ field.label }}</dt>
              <dd :class="{ 'sp-mono': field.mono }">{{ field.value }}</dd>
            </template>
          </dl>
        </div>
      </section>

      <section class="sp-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">{{ zhCN.p06.sections.beforeAfter }}</div>
        </div>
        <div class="sp-panel__body">
          <BeforeAfterTable :rows="order.before_after" />
        </div>
      </section>

      <div class="sp-p06__grid">
        <section class="sp-panel">
          <div class="sp-panel__header">
            <div class="sp-panel__title">{{ zhCN.p06.sections.impact }}</div>
          </div>
          <div class="sp-panel__body">
            <p v-if="order.impact_scope" class="sp-p06__impact">{{ order.impact_scope }}</p>
            <p v-else class="sp-faint">{{ zhCN.p06.rollback.impactEmpty }}</p>
          </div>
        </section>

        <section class="sp-panel">
          <div class="sp-panel__header">
            <div class="sp-panel__title">{{ zhCN.p06.sections.evidence }}</div>
          </div>
          <div class="sp-panel__body">
            <EvidencePack :items="order.evidence" :complete="order.evidence_complete" />
          </div>
        </section>
      </div>

      <div class="sp-p06__grid">
        <section class="sp-panel">
          <div class="sp-panel__header">
            <div class="sp-panel__title">{{ zhCN.p06.sections.rollback }}</div>
          </div>
          <div class="sp-panel__body">
            <RollbackPanel :plan="order.rollback_plan" />
          </div>
        </section>

        <section class="sp-panel">
          <div class="sp-panel__header">
            <div class="sp-panel__title">{{ zhCN.p06.sections.actions }}</div>
          </div>
          <div class="sp-panel__body">
            <ApprovalActions
              :readonly="readonlyView"
              :readonly-copy="readonlyCopy"
              :can-approve="canApprove"
              :status="order.status"
              :plan-status="order.plan_status"
              :role="role"
              :has-execution="Boolean(order.execution)"
              :pending-action="transferPending ? 'transfer' : actionPending ? dialogMode : null"
              @approve="openAction('approve')"
              @reject="openAction('reject')"
              @transfer="openTransfer"
              @withdraw="openAction('withdraw')"
              @compensate="openAction('compensate')"
            />
          </div>
        </section>
      </div>

      <section v-if="order.execution" class="sp-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">{{ zhCN.p06.sections.execution }}</div>
        </div>
        <div class="sp-panel__body">
          <ExecutionPanel :execution="order.execution" :plan-status="order.plan_status" />
        </div>
      </section>

      <section class="sp-panel">
        <div class="sp-panel__header">
          <div class="sp-panel__title">{{ zhCN.p06.sections.timeline }}</div>
        </div>
        <div class="sp-panel__body">
          <ResultTimeline :entries="order.result_timeline" />
        </div>
      </section>
    </template>

    <ActionDialog
      :open="dialogOpen"
      :title="dialogConfig.title"
      :description="dialogConfig.description"
      :field-label="dialogConfig.fieldLabel"
      :placeholder="dialogConfig.placeholder"
      :confirm-label="dialogConfig.confirmLabel"
      :required="dialogConfig.required"
      multiline
      :pending="actionPending"
      :error="dialogError"
      @confirm="submitAction"
      @cancel="closeAction"
    />

    <TransferDialog
      :open="transferOpen"
      :title="zhCN.p06.actions.transferTitle"
      :description="zhCN.p06.actions.transferBody"
      :approver-label="zhCN.p06.actions.transferApproverLabel"
      :approver-placeholder="zhCN.p06.actions.transferApproverPlaceholder"
      :reason-label="zhCN.p06.actions.transferReasonLabel"
      :reason-placeholder="zhCN.p06.actions.transferReasonPlaceholder"
      :confirm-label="zhCN.p06.actions.transferConfirm"
      :pending="transferPending"
      :error="transferError"
      @confirm="submitTransfer"
      @cancel="closeTransfer"
    />
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p06__summary-body {
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 11px 14px;
}

.sp-p06__summary-top {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.sp-p06__order-no {
  font-size: 14px;
  font-weight: 650;
  color: var(--sp-text);
}

.sp-p06__hash {
  padding: 1px 6px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 10.5px;
  color: var(--sp-muted);
  cursor: help;
}

.sp-p06__summary-grid {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr) 92px minmax(0, 1fr);
  gap: 4px 10px;
  margin: 0;
  padding: 9px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 11.5px;
}

.sp-p06__summary-grid dt {
  color: var(--sp-muted);
}

.sp-p06__summary-grid dd {
  margin: 0;
  min-width: 0;
  color: var(--sp-text);
  word-break: break-word;
}

.sp-p06__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  gap: 14px;
  align-items: start;
}

.sp-p06__grid > .sp-panel {
  align-self: start;
}

.sp-p06__impact {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--sp-text);
}

@media (max-width: 980px) {
  .sp-p06__grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .sp-p06__summary-grid {
    grid-template-columns: 92px minmax(0, 1fr);
  }
}
</style>
