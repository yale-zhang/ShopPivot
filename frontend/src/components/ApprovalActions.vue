<script setup lang="ts">
import { computed } from 'vue'
import { ElButton } from 'element-plus'

import { zhCN, READONLY_COPY } from '../i18n/zh-CN'

const props = withDefaults(
  defineProps<{
    readonly: boolean
    readonlyCopy?: string
    canApprove?: boolean
    status?: string
    planStatus?: string | null
    role?: string
    hasExecution?: boolean
    pendingAction?: string | null
  }>(),
  {
    readonlyCopy: READONLY_COPY,
    canApprove: false,
    status: '',
    planStatus: null,
    role: '',
    hasExecution: false,
    pendingAction: null,
  },
)

const emit = defineEmits<{
  (event: 'approve'): void
  (event: 'reject'): void
  (event: 'transfer'): void
  (event: 'withdraw'): void
  (event: 'compensate'): void
}>()

const approveEnabled = computed(
  () => props.canApprove && props.status === 'PENDING' && !props.pendingAction,
)
const rejectEnabled = computed(
  () => props.canApprove && props.status === 'PENDING' && !props.pendingAction,
)
const transferEnabled = computed(
  () => props.canApprove && props.status === 'PENDING' && !props.pendingAction,
)
const withdrawEnabled = computed(
  () =>
    props.planStatus === 'APPROVED' && !props.hasExecution && !props.pendingAction,
)
const showCompensate = computed(
  () => props.planStatus === 'VERIFIED' && props.role === 'OWNER',
)
const compensateEnabled = computed(() => showCompensate.value && !props.pendingAction)

function approveTitle(): string {
  return approveEnabled.value ? zhCN.p06.actions.approve : props.readonlyCopy
}

function rejectTitle(): string {
  return rejectEnabled.value ? zhCN.p06.actions.reject : props.readonlyCopy
}

function transferTitle(): string {
  return transferEnabled.value ? zhCN.p06.actions.transfer : props.readonlyCopy
}

function withdrawTitle(): string {
  return withdrawEnabled.value ? zhCN.p06.actions.withdraw : props.readonlyCopy
}

function compensateTitle(): string {
  return compensateEnabled.value ? zhCN.p06.actions.compensate : props.readonlyCopy
}

function emitAction(action: 'approve' | 'reject' | 'transfer' | 'withdraw' | 'compensate'): void {
  if (props.pendingAction) return
  if (action === 'approve' && !approveEnabled.value) return
  if (action === 'reject' && !rejectEnabled.value) return
  if (action === 'transfer') {
    if (!transferEnabled.value) return
    emit('transfer')
    return
  }
  if (action === 'withdraw' && !withdrawEnabled.value) return
  if (action === 'compensate' && !compensateEnabled.value) return
  if (action === 'approve') emit('approve')
  else if (action === 'reject') emit('reject')
  else if (action === 'withdraw') emit('withdraw')
  else emit('compensate')
}
</script>

<template>
  <div class="sp-approval">
    <div class="sp-approval__buttons">
      <ElButton
        type="primary"
        data-action="approve"
        :disabled="!approveEnabled"
        :title="approveTitle()"
        :loading="pendingAction === 'approve'"
        @click="emitAction('approve')"
      >
        {{ zhCN.p06.actions.approve }}
      </ElButton>
      <ElButton
        type="danger"
        plain
        data-action="reject"
        :disabled="!rejectEnabled"
        :title="rejectTitle()"
        :loading="pendingAction === 'reject'"
        @click="emitAction('reject')"
      >
        {{ zhCN.p06.actions.reject }}
      </ElButton>
      <ElButton
        data-action="transfer"
        :disabled="!transferEnabled"
        :title="transferTitle()"
        :loading="pendingAction === 'transfer'"
        @click="emitAction('transfer')"
      >
        {{ zhCN.p06.actions.transfer }}
      </ElButton>
      <ElButton
        data-action="withdraw"
        :disabled="!withdrawEnabled"
        :title="withdrawTitle()"
        :loading="pendingAction === 'withdraw'"
        @click="emitAction('withdraw')"
      >
        {{ zhCN.p06.actions.withdraw }}
      </ElButton>
      <ElButton
        v-if="showCompensate"
        type="warning"
        plain
        data-action="compensate"
        :disabled="!compensateEnabled"
        :title="compensateTitle()"
        :loading="pendingAction === 'compensate'"
        @click="emitAction('compensate')"
      >
        {{ zhCN.p06.actions.compensate }}
      </ElButton>
    </div>
    <div v-if="readonly" class="sp-approval__readonly" role="note">
      <span class="sp-approval__lock" aria-hidden="true">●</span>
      <span>{{ readonlyCopy }}</span>
    </div>
  </div>
</template>

<style scoped>
.sp-approval {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 9px 14px;
}

.sp-approval__buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sp-approval__readonly {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border: 1px solid var(--sp-readonly-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-readonly-soft);
  color: var(--sp-readonly);
  font-size: 11.5px;
}

.sp-approval__lock {
  font-size: 7px;
  line-height: 1;
  color: var(--sp-readonly);
}
</style>
