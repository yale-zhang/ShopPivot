<script setup lang="ts">
import { computed } from 'vue'

import { zhCN } from '../i18n/zh-CN'

type StateKind = 'loading' | 'empty' | 'error' | 'forbidden' | 'notFound'

const props = defineProps<{
  state?: StateKind
  title?: string
  description?: string
  code?: string
  compact?: boolean
  retryable?: boolean
}>()

const emit = defineEmits<{ (event: 'retry'): void }>()

const defaultTitle = computed(() => {
  switch (props.state) {
    case 'loading':
      return zhCN.states.loading
    case 'error':
      return zhCN.states.error
    case 'forbidden':
      return zhCN.states.forbidden
    case 'notFound':
      return zhCN.states.notFound
    case 'empty':
    default:
      return zhCN.states.emptyReport
  }
})

const defaultDescription = computed(() => {
  switch (props.state) {
    case 'error':
      return zhCN.states.loadFailedHint
    case 'forbidden':
      return zhCN.states.forbiddenHint
    case 'notFound':
      return zhCN.states.notFoundHint
    default:
      return ''
  }
})

const resolvedTitle = computed(() => props.title ?? defaultTitle.value)
const resolvedDescription = computed(() => props.description ?? defaultDescription.value)
const showRetry = computed(
  () => props.retryable ?? (props.state === 'error' || props.state === 'forbidden'),
)
</script>

<template>
  <div
    class="sp-state"
    :class="[`sp-state--${state ?? 'empty'}`, { 'sp-state--compact': compact }]"
    :role="state === 'error' ? 'alert' : 'status'"
  >
    <div v-if="state === 'loading'" class="sp-state__skeleton" aria-hidden="true">
      <span class="sp-state__line sp-state__line--short" />
      <span class="sp-state__line" />
      <span class="sp-state__line sp-state__line--mid" />
    </div>
    <div class="sp-state__title">{{ resolvedTitle }}</div>
    <p v-if="resolvedDescription" class="sp-state__description">{{ resolvedDescription }}</p>
    <span v-if="code" class="sp-state__code">{{ code }}</span>
    <div v-if="$slots.default || (showRetry && state !== 'loading')" class="sp-state__actions">
      <slot />
      <button
        v-if="showRetry && state !== 'loading'"
        type="button"
        class="sp-state__retry"
        @click="emit('retry')"
      >
        {{ zhCN.states.retry }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.sp-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 190px;
  padding: 28px 18px;
  text-align: center;
  background: var(--sp-surface);
  border: 1px dashed var(--sp-border-strong);
  border-radius: var(--sp-radius);
}

.sp-state--compact {
  min-height: 108px;
  padding: 18px 14px;
}

.sp-state--error {
  border-color: var(--sp-danger-border);
  background: var(--sp-danger-soft);
}

.sp-state--forbidden {
  border-color: var(--sp-warning-border);
  background: var(--sp-warning-soft);
}

.sp-state__title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--sp-text);
  line-height: 1.5;
}

.sp-state__description {
  max-width: 560px;
  font-size: 12px;
  color: var(--sp-muted);
}

.sp-state__code {
  margin-top: 1px;
  padding: 1px 6px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface);
  font-family: var(--sp-font-mono);
  font-size: 11px;
  color: var(--sp-muted);
}

.sp-state__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 5px;
}

.sp-state__retry {
  height: 27px;
  padding: 0 11px;
  border: 1px solid var(--sp-border-strong);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  font-size: 12px;
  color: var(--sp-text);
}
.sp-state__retry:hover {
  border-color: var(--sp-primary);
  color: var(--sp-primary);
}

.sp-state__skeleton {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  width: 100%;
  max-width: 280px;
  margin-bottom: 5px;
}

.sp-state__line {
  display: block;
  width: 100%;
  height: 7px;
  border-radius: 2px;
  background: var(--sp-surface-sunken);
}

.sp-state__line--short {
  width: 42%;
}
.sp-state__line--mid {
  width: 72%;
}
</style>
