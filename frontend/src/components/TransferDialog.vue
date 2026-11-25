<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElButton } from 'element-plus'

import { zhCN } from '../i18n/zh-CN'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    description?: string
    approverLabel: string
    approverPlaceholder?: string
    reasonLabel: string
    reasonPlaceholder?: string
    confirmLabel: string
    cancelLabel?: string
    pending?: boolean
    error?: string
  }>(),
  {
    description: '',
    approverPlaceholder: '',
    reasonPlaceholder: '',
    cancelLabel: zhCN.components.actionDialog.cancel,
    pending: false,
    error: '',
  },
)

const emit = defineEmits<{
  (event: 'confirm', payload: { approver: string; reason: string }): void
  (event: 'cancel'): void
}>()

const approver = ref('')
const reason = ref('')
const localError = ref('')
const approverRef = ref<HTMLInputElement | null>(null)

const displayError = computed(() => localError.value || props.error)

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && !props.pending) {
    event.stopPropagation()
    emit('cancel')
  }
}

function submit(): void {
  if (props.pending) return
  const approverValue = approver.value.trim()
  if (!approverValue) {
    localError.value = zhCN.p06.actions.transferApproverRequired
    approverRef.value?.focus()
    return
  }
  localError.value = ''
  emit('confirm', { approver: approverValue, reason: reason.value.trim() })
}

function cancel(): void {
  if (props.pending) return
  emit('cancel')
}

watch(
  () => props.open,
  async (open) => {
    if (typeof document === 'undefined') return
    if (open) {
      approver.value = ''
      reason.value = ''
      localError.value = ''
      document.addEventListener('keydown', onKeydown)
      await nextTick()
      approverRef.value?.focus()
    } else {
      document.removeEventListener('keydown', onKeydown)
    }
  },
  { immediate: true },
)

watch(
  () => props.error,
  () => {
    if (props.error) localError.value = ''
  },
)

onBeforeUnmount(() => {
  if (typeof document === 'undefined') return
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="sp-action">
      <div v-if="open" class="sp-action-root" :style="{ zIndex: 2100 }">
        <div class="sp-action__overlay" aria-hidden="true" @click="cancel" />
        <div class="sp-action sp-transfer" role="dialog" aria-modal="true" :aria-label="title">
          <h2 class="sp-action__title">{{ title }}</h2>
          <p v-if="description" class="sp-action__description">{{ description }}</p>
          <label class="sp-action__field">
            <span class="sp-action__label">{{ approverLabel }}</span>
            <input
              ref="approverRef"
              v-model="approver"
              data-field="approver"
              class="sp-action__control"
              type="text"
              :placeholder="approverPlaceholder"
              :disabled="pending"
            />
          </label>
          <label class="sp-action__field">
            <span class="sp-action__label">{{ reasonLabel }}</span>
            <textarea
              v-model="reason"
              data-field="reason"
              class="sp-action__control sp-action__control--textarea"
              :placeholder="reasonPlaceholder"
              rows="3"
              :disabled="pending"
            />
          </label>
          <p v-if="displayError" class="sp-action__error" role="alert">{{ displayError }}</p>
          <footer class="sp-action__footer">
            <ElButton size="small" :disabled="pending" @click="cancel">{{ cancelLabel }}</ElButton>
            <ElButton
              size="small"
              type="primary"
              data-role="transfer-confirm"
              :loading="pending"
              :disabled="pending"
              @click="submit"
            >
              {{ confirmLabel }}
            </ElButton>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.sp-action-root {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.sp-action__overlay {
  position: absolute;
  inset: 0;
  background: rgba(31, 42, 48, 0.38);
}

.sp-action {
  position: relative;
  width: min(440px, 100%);
  padding: 16px;
  background: var(--sp-surface);
  border: 1px solid var(--sp-border-strong);
  border-radius: var(--sp-radius);
  box-shadow: var(--sp-shadow-modal);
}

.sp-action__title {
  font-size: 14px;
  font-weight: 650;
  color: var(--sp-text);
}

.sp-action__description {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--sp-muted);
}

.sp-action__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 12px;
}

.sp-action__label {
  font-size: 11px;
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-action__control {
  width: 100%;
  height: 30px;
  padding: 0 9px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  font-size: 12.5px;
  color: var(--sp-text);
}

.sp-action__control:focus {
  border-color: var(--sp-primary);
  outline: none;
}

.sp-action__control--textarea {
  height: auto;
  padding: 7px 9px;
  line-height: 1.55;
  resize: vertical;
}

.sp-action__error {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--sp-danger);
}

.sp-action__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--sp-border);
}

.sp-action-enter-active,
.sp-action-leave-active {
  transition: opacity 120ms ease;
}
.sp-action-enter-from,
.sp-action-leave-to {
  opacity: 0;
}
</style>
