<script setup lang="ts">
import { computed } from 'vue'

import type { ChangeOrderEvidence } from '../api/types'
import { zhCN } from '../i18n/zh-CN'

const props = defineProps<{
  items: ChangeOrderEvidence[]
  complete: boolean
}>()

const missing = computed(() => !props.complete || props.items.length === 0)
</script>

<template>
  <div class="sp-evidence">
    <div v-if="missing" class="sp-evidence__banner sp-evidence__banner--danger" role="alert">
      <span class="sp-evidence__mark" aria-hidden="true">!</span>
      {{ zhCN.p06.evidence.missing }}
    </div>
    <div v-else class="sp-evidence__banner sp-evidence__banner--ok">
      <span class="sp-evidence__mark" aria-hidden="true">✓</span>
      {{ zhCN.p06.evidence.complete }}
    </div>

    <ul v-if="items.length" class="sp-evidence__list">
      <li v-for="(item, index) in items" :key="`${item.kind}-${item.ref}-${index}`" class="sp-evidence__item">
        <div class="sp-evidence__row">
          <span class="sp-chip sp-chip--primary">{{ item.kind }}</span>
          <span class="sp-evidence__label">{{ item.label }}</span>
        </div>
        <div class="sp-evidence__ref sp-mono-break">{{ item.ref }}</div>
      </li>
    </ul>
    <div v-else class="sp-evidence__empty">{{ zhCN.p06.evidence.empty }}</div>
  </div>
</template>

<style scoped>
.sp-evidence {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.sp-evidence__banner {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  font-size: 12px;
  font-weight: 500;
}

.sp-evidence__banner--danger {
  background: var(--sp-danger-soft);
  border-color: var(--sp-danger-border);
  color: var(--sp-danger);
}

.sp-evidence__banner--ok {
  background: var(--sp-success-soft);
  border-color: var(--sp-success-border);
  color: var(--sp-success);
}

.sp-evidence__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 15px;
  height: 15px;
  border: 1px solid currentColor;
  border-radius: 50%;
  font-family: var(--sp-font-mono);
  font-size: 10px;
  line-height: 1;
  flex: none;
}

.sp-evidence__list {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  overflow: hidden;
}

.sp-evidence__item {
  padding: 7px 10px;
  border-bottom: 1px solid var(--sp-border);
  background: var(--sp-surface);
}

.sp-evidence__item:last-child {
  border-bottom: 0;
}

.sp-evidence__row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sp-evidence__label {
  font-size: 12px;
  color: var(--sp-text);
}

.sp-evidence__ref {
  margin-top: 2px;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-evidence__empty {
  padding: 14px;
  text-align: center;
  font-size: 12px;
  color: var(--sp-muted);
  border: 1px dashed var(--sp-border);
  border-radius: var(--sp-radius-sm);
}
</style>
