<script setup lang="ts">
import { computed } from 'vue'

import { zhCN } from '../i18n/zh-CN'

type TodoTabKey = 'all' | 'approval' | 'exception'

const props = defineProps<{
  active: TodoTabKey
  counts: Record<TodoTabKey, number>
}>()

const emit = defineEmits<{ (event: 'update:active', value: TodoTabKey): void }>()

const tabs = computed<Array<{ key: TodoTabKey; label: string }>>(() => [
  { key: 'all', label: zhCN.p05.tabs.all },
  { key: 'approval', label: zhCN.p05.tabs.approval },
  { key: 'exception', label: zhCN.p05.tabs.exception },
])
</script>

<template>
  <div class="sp-todo-tabs" role="tablist" :aria-label="zhCN.p05.title">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      type="button"
      role="tab"
      class="sp-todo-tabs__tab"
      :class="{ 'is-active': props.active === tab.key }"
      :aria-selected="props.active === tab.key"
      @click="emit('update:active', tab.key)"
    >
      <span class="sp-todo-tabs__label">{{ tab.label }}</span>
      <span class="sp-todo-tabs__count">{{ props.counts[tab.key] ?? 0 }}</span>
    </button>
  </div>
</template>

<style scoped>
.sp-todo-tabs {
  display: flex;
  align-items: stretch;
  gap: 2px;
  border-bottom: 1px solid var(--sp-border);
}

.sp-todo-tabs__tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 14px;
  border: 0;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  background: transparent;
  color: var(--sp-muted);
  font-size: 12.5px;
  font-weight: 500;
}

.sp-todo-tabs__tab:hover {
  color: var(--sp-text);
  background: var(--sp-surface-sunken);
}

.sp-todo-tabs__tab.is-active {
  color: var(--sp-primary);
  border-bottom-color: var(--sp-primary);
  background: transparent;
}

.sp-todo-tabs__count {
  min-width: 18px;
  padding: 0 4px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-pill);
  background: var(--sp-surface-sunken);
  font-family: var(--sp-font-mono);
  font-size: 10px;
  line-height: 15px;
  text-align: center;
  color: var(--sp-muted);
}

.sp-todo-tabs__tab.is-active .sp-todo-tabs__count {
  background: var(--sp-primary-soft);
  border-color: var(--sp-primary-soft-strong);
  color: var(--sp-primary);
}
</style>
