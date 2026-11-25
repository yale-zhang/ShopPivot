<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import { zhCN } from '../i18n/zh-CN'
import { useShellStore } from '../stores/shell'
import { formatShortDateTime } from '../utils/format'
import StatusBadge from '../components/StatusBadge.vue'

const shell = useShellStore()

const runIdText = computed(() => shell.runId || zhCN.status.noRun)
const collectedText = computed(
  () => formatShortDateTime(shell.lastCollectedAt) || zhCN.common.none,
)
</script>

<template>
  <div class="sp-status-bar" role="status" :aria-label="zhCN.status.label">
    <div class="sp-status-bar__item">
      <span class="sp-status-bar__label">{{ zhCN.status.runId }}</span>
      <span class="sp-status-bar__value sp-mono" :title="shell.runId || zhCN.status.noRun">
        {{ runIdText }}
      </span>
    </div>
    <span class="sp-status-bar__sep" aria-hidden="true" />
    <div class="sp-status-bar__item">
      <span class="sp-status-bar__label">{{ zhCN.status.lastCollected }}</span>
      <span class="sp-status-bar__value sp-mono">{{ collectedText }}</span>
    </div>
    <span class="sp-status-bar__sep" aria-hidden="true" />
    <div class="sp-status-bar__item">
      <span class="sp-status-bar__label">{{ zhCN.status.todos }}</span>
      <RouterLink to="/p05" class="sp-status-bar__value sp-status-bar__link">
        {{ shell.todoCount }}
      </RouterLink>
    </div>
    <span class="sp-status-bar__sep" aria-hidden="true" />
    <div class="sp-status-bar__item">
      <span class="sp-status-bar__label">{{ zhCN.status.workers }}</span>
      <span class="sp-status-bar__value sp-mono">{{ shell.workerOnline }}</span>
      <span class="sp-status-bar__unit">{{ zhCN.status.online }}</span>
    </div>
    <span class="sp-status-bar__spacer" />
    <span v-if="shell.statusError" class="sp-status-bar__error" :title="shell.statusError">
      {{ shell.statusError }}
    </span>
    <StatusBadge :label="zhCN.status.readonly" tone="neutral" />
  </div>
</template>

<style scoped>
.sp-status-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  height: var(--sp-status-height);
  padding: 0 18px;
  background: var(--sp-surface-sunken);
  border-bottom: 1px solid var(--sp-border);
  font-size: 10.5px;
  color: var(--sp-muted);
  overflow: hidden;
}

.sp-status-bar__item {
  display: flex;
  align-items: baseline;
  gap: 5px;
  min-width: 0;
  white-space: nowrap;
}

.sp-status-bar__label {
  color: var(--sp-faint);
  letter-spacing: 0.03em;
}

.sp-status-bar__value {
  color: var(--sp-text);
  font-size: 11px;
}

.sp-status-bar__item:first-child .sp-status-bar__value {
  max-width: 230px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sp-status-bar__link {
  color: var(--sp-primary);
  text-decoration: none;
}
.sp-status-bar__link:hover {
  text-decoration: underline;
}

.sp-status-bar__unit {
  color: var(--sp-faint);
}

.sp-status-bar__sep {
  width: 1px;
  height: 12px;
  background: var(--sp-border);
  flex: none;
}

.sp-status-bar__spacer {
  flex: 1;
}

.sp-status-bar__error {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--sp-danger);
}

@media (max-width: 760px) {
  .sp-status-bar {
    gap: 7px;
    padding: 0 12px;
  }
  .sp-status-bar__item:first-child .sp-status-bar__value {
    max-width: 150px;
  }
  .sp-status-bar__error {
    display: none;
  }
}
</style>
