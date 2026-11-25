<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElButton } from 'element-plus'

import { zhCN } from '../i18n/zh-CN'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    body?: string
    confirmLabel?: string
    cancelLabel?: string
    danger?: boolean
    pending?: boolean
  }>(),
  {
    title: zhCN.components.confirm.title,
    body: '',
    confirmLabel: zhCN.components.confirm.confirm,
    cancelLabel: zhCN.components.confirm.cancel,
    danger: false,
    pending: false,
  },
)

const emit = defineEmits<{
  (event: 'confirm'): void
  (event: 'cancel'): void
}>()

const modalRef = ref<HTMLElement | null>(null)

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && !props.pending) {
    event.stopPropagation()
    emit('cancel')
  }
}

watch(
  () => props.open,
  async (open) => {
    if (typeof document === 'undefined') return
    if (open) {
      document.addEventListener('keydown', onKeydown)
      await nextTick()
      modalRef.value?.focus()
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
    <Transition name="sp-modal">
      <div v-if="open" class="sp-modal-root" :style="{ zIndex: 2000 }">
        <div class="sp-modal__overlay" aria-hidden="true" @click="!pending && emit('cancel')" />
        <div
          ref="modalRef"
          class="sp-modal"
          role="alertdialog"
          aria-modal="true"
          :aria-label="title"
          tabindex="-1"
        >
          <h2 class="sp-modal__title">{{ title }}</h2>
          <div class="sp-modal__body">
            <slot>{{ body }}</slot>
          </div>
          <footer class="sp-modal__footer">
            <ElButton size="small" :disabled="pending" @click="emit('cancel')">
              {{ cancelLabel }}
            </ElButton>
            <ElButton
              size="small"
              :type="danger ? 'danger' : 'primary'"
              :loading="pending"
              :disabled="pending"
              @click="emit('confirm')"
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
.sp-modal-root {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.sp-modal__overlay {
  position: absolute;
  inset: 0;
  background: rgba(31, 42, 48, 0.38);
}

.sp-modal {
  position: relative;
  width: min(440px, 100%);
  padding: 16px;
  background: var(--sp-surface);
  border: 1px solid var(--sp-border-strong);
  border-radius: var(--sp-radius);
  box-shadow: var(--sp-shadow-modal);
}

.sp-modal__title {
  font-size: 14px;
  font-weight: 650;
  color: var(--sp-text);
}

.sp-modal__body {
  margin-top: 8px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--sp-muted);
  word-break: break-word;
}

.sp-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--sp-border);
}

.sp-modal-enter-active,
.sp-modal-leave-active {
  transition: opacity 120ms ease;
}
.sp-modal-enter-from,
.sp-modal-leave-to {
  opacity: 0;
}
</style>
