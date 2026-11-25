<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { zhCN } from '../i18n/zh-CN'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    subtitle?: string
    width?: string
    zIndex?: number
    closeLabel?: string
  }>(),
  {
    subtitle: '',
    width: '540px',
    zIndex: 1000,
    closeLabel: zhCN.components.drawer.close,
  },
)

const emit = defineEmits<{ (event: 'close'): void }>()

const closeRef = ref<HTMLButtonElement | null>(null)
let previousOverflow = ''
let previousActive: HTMLElement | null = null

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.stopPropagation()
    emit('close')
  }
}

watch(
  () => props.open,
  async (open) => {
    if (typeof document === 'undefined') return
    if (open) {
      previousOverflow = document.body.style.overflow
      previousActive = document.activeElement instanceof HTMLElement ? document.activeElement : null
      document.body.style.overflow = 'hidden'
      document.addEventListener('keydown', onKeydown)
      await nextTick()
      closeRef.value?.focus()
    } else {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeydown)
      previousActive?.focus?.()
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (typeof document === 'undefined') return
  document.body.style.overflow = previousOverflow
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="sp-drawer">
      <div
        v-if="open"
        class="sp-drawer-root"
        :style="{ zIndex }"
      >
        <div class="sp-drawer__overlay" aria-hidden="true" @click="emit('close')" />
        <aside
          class="sp-drawer__panel"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
          :style="{ width }"
        >
          <header class="sp-drawer__header">
            <div class="sp-drawer__heading">
              <h2 class="sp-drawer__title">{{ title }}</h2>
              <p v-if="subtitle" class="sp-drawer__subtitle">{{ subtitle }}</p>
            </div>
            <button
              ref="closeRef"
              type="button"
              class="sp-drawer__close"
              :aria-label="closeLabel"
              :title="closeLabel"
              @click="emit('close')"
            >
              ×
            </button>
          </header>
          <div class="sp-drawer__body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="sp-drawer__footer">
            <slot name="footer" />
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.sp-drawer-root {
  position: fixed;
  inset: 0;
  display: flex;
  justify-content: flex-end;
}

.sp-drawer__overlay {
  position: absolute;
  inset: 0;
  background: rgba(31, 42, 48, 0.34);
}

.sp-drawer__panel {
  position: relative;
  display: flex;
  flex-direction: column;
  max-width: 96vw;
  height: 100%;
  background: var(--sp-surface);
  border-left: 1px solid var(--sp-border-strong);
  box-shadow: var(--sp-shadow-drawer);
  outline: none;
}

.sp-drawer__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--sp-border);
  background: var(--sp-surface-sunken);
}

.sp-drawer__heading {
  min-width: 0;
}

.sp-drawer__title {
  font-size: 15px;
  font-weight: 650;
  line-height: 1.35;
  color: var(--sp-text);
}

.sp-drawer__subtitle {
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--sp-muted);
}

.sp-drawer__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  color: var(--sp-muted);
  font-size: 18px;
  line-height: 1;
  flex: none;
}

.sp-drawer__close:hover {
  border-color: var(--sp-border-strong);
  color: var(--sp-text);
}

.sp-drawer__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px;
}

.sp-drawer__footer {
  padding: 10px 16px;
  border-top: 1px solid var(--sp-border);
  background: var(--sp-surface-sunken);
}

.sp-drawer-enter-active,
.sp-drawer-leave-active {
  transition: opacity 140ms ease;
}
.sp-drawer-enter-active .sp-drawer__panel,
.sp-drawer-leave-active .sp-drawer__panel {
  transition: transform 140ms ease;
}
.sp-drawer-enter-from,
.sp-drawer-leave-to {
  opacity: 0;
}
.sp-drawer-enter-from .sp-drawer__panel,
.sp-drawer-leave-to .sp-drawer__panel {
  transform: translateX(24px);
}
</style>
