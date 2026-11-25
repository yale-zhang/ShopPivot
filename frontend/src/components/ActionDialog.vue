<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElButton } from 'element-plus'

import { zhCN } from '../i18n/zh-CN'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    description?: string
    fieldLabel: string
    placeholder?: string
    confirmLabel: string
    cancelLabel?: string
    required?: boolean
    multiline?: boolean
    pending?: boolean
    error?: string
  }>(),
  {
    description: '',
    placeholder: '',
    cancelLabel: zhCN.components.actionDialog.cancel,
    required: false,
    multiline: false,
    pending: false,
    error: '',
  },
)

const emit = defineEmits<{
  (event: 'confirm', value: string): void
  (event: 'cancel'): void
}>()

const value = ref('')
const localError = ref('')
const fieldRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

const displayError = computed(() => localError.value || props.error)

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && !props.pending) {
    event.stopPropagation()
    emit('cancel')
  }
}

function submit(): void {
  if (props.pending) return
  const trimmed = value.value.trim()
  if (props.required && !trimmed) {
    localError.value = zhCN.components.actionDialog.required
    fieldRef.value?.focus()
    return
  }
  localError.value = ''
  emit('confirm', trimmed)
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
      value.value = ''
      localError.value = ''
      document.addEventListener('keydown', onKeydown)
      await nextTick()
      fieldRef.value?.focus()
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
        <div class="sp-action" role="dialog" aria-modal="true" :aria-label="title">
          <h2 class="sp-action__title">{{ title }}</h2>
          <p v-if="description" class="sp-action__description">{{ description }}</p>
          <label class="sp-action__field">
            <span class="sp-action__label">{{ fieldLabel }}</span>
            <textarea
              v-if="multiline"
              ref="fieldRef"
              v-model="value"
              class="sp-action__control sp-action__control--textarea"
              :placeholder="placeholder"
              rows="3"
              :disabled="pending"
            />
            <input
              v-else
              ref="fieldRef"
              v-model="value"
              class="sp-action__control"
              type="text"
              :placeholder="placeholder"
              :disabled="pending"
            />
          </label>
          <p v-if="displayError" class="sp-action__error" role="alert">{{ displayError }}</p>
          <footer class="sp-action__footer">
            <ElButton size="small" :disabled="pending" @click="cancel">{{ cancelLabel }}</ElButton>
            <ElButton size="small" type="primary" :loading="pending" :disabled="pending" @click="submit">
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

.sp-action__control--textarea {
  height: auto;
  min-height: 68px;
  padding: 7px 9px;
  line-height: 1.5;
  resize: vertical;
}

.sp-action__control:focus {
  outline: none;
  border-color: var(--sp-primary);
  box-shadow: var(--sp-focus);
}

.sp-action__error {
  margin-top: 7px;
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
