<script setup lang="ts">
import { ElButton } from 'element-plus'

import type { ModuleInfo } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { labelForModuleState, toneForStatus } from '../utils/status'
import StateView from './StateView.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  modules: ModuleInfo[]
  canDisable?: boolean
  pendingName?: string
}>()

const emit = defineEmits<{ (event: 'disable', module: ModuleInfo): void }>()

function isDisabled(module: ModuleInfo): boolean {
  return module.state === 'DISABLED' || !module.enabled
}

function displayState(module: ModuleInfo): string {
  if (module.state === 'REJECTED') return 'REJECTED'
  return module.enabled ? module.state : 'DISABLED'
}

function canAct(module: ModuleInfo): boolean {
  return Boolean(props.canDisable) && !module.core
}

function disableLabel(module: ModuleInfo): string {
  return isDisabled(module) ? zhCN.p09.disabled : zhCN.p09.disable
}

function onDisable(module: ModuleInfo): void {
  if (!canAct(module) || isDisabled(module)) return
  emit('disable', module)
}
</script>

<template>
  <div v-if="modules.length" class="sp-modules">
    <table class="sp-modules__table">
      <thead>
        <tr>
          <th scope="col">{{ zhCN.p09.columns.name }}</th>
          <th scope="col">{{ zhCN.p09.columns.category }}</th>
          <th scope="col">{{ zhCN.p09.columns.version }}</th>
          <th scope="col">{{ zhCN.p09.columns.state }}</th>
          <th scope="col">{{ zhCN.p09.columns.contributions }}</th>
          <th scope="col" class="is-center">{{ zhCN.p09.columns.core }}</th>
          <th scope="col" class="is-right">{{ zhCN.common.action }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="module in modules" :key="module.name" :class="{ 'is-disabled': displayState(module) === 'DISABLED' }">
          <td>
            <div class="sp-modules__name sp-mono">{{ module.name }}</div>
            <div v-if="module.blocking_reason" class="sp-modules__blocking">
              {{ module.blocking_reason }}
            </div>
          </td>
          <td>
            <span class="sp-chip">{{ module.category }}</span>
          </td>
          <td class="sp-mono sp-modules__version">{{ module.version }}</td>
          <td>
            <StatusBadge
              :label="labelForModuleState(displayState(module))"
              :tone="toneForStatus(displayState(module))"
              dot
            />
          </td>
          <td>
            <div v-if="module.contributions.length" class="sp-modules__contributions">
              <span
                v-for="contribution in module.contributions"
                :key="`${contribution.kind}-${contribution.id}`"
                class="sp-chip"
                :title="zhCN.p09.contributionKind(contribution.kind)"
              >
                {{ contribution.id }}
              </span>
            </div>
            <span v-else class="sp-faint">{{ zhCN.p09.noContribution }}</span>
          </td>
          <td class="is-center">
            <span v-if="module.core" class="sp-modules__core">{{ zhCN.p09.coreYes }}</span>
            <span v-else class="sp-faint">{{ zhCN.p09.coreNo }}</span>
          </td>
          <td class="is-right">
            <ElButton
              v-if="canAct(module)"
              size="small"
              :disabled="isDisabled(module) || pendingName === module.name"
              :loading="pendingName === module.name"
              @click="onDisable(module)"
            >
              {{ disableLabel(module) }}
            </ElButton>
            <span v-else-if="!module.core && !canDisable" class="sp-faint sp-modules__owner-only">
              {{ zhCN.p09.onlyOwner }}
            </span>
            <span v-else class="sp-faint">{{ zhCN.common.none }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <StateView v-else state="empty" :title="zhCN.p09.emptyModules" compact />
</template>

<style scoped>
.sp-modules {
  overflow-x: auto;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
}

.sp-modules__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}

.sp-modules__table th {
  padding: 7px 10px;
  background: var(--sp-surface-sunken);
  border-bottom: 1px solid var(--sp-border);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--sp-muted);
  text-align: left;
  white-space: nowrap;
}

.sp-modules__table td {
  padding: 9px 10px;
  border-bottom: 1px solid var(--sp-border);
  vertical-align: middle;
}

.sp-modules__table tbody tr:last-child td {
  border-bottom: 0;
}

.sp-modules__table tbody tr:hover {
  background: #f7fafb;
}

.sp-modules__table tr.is-disabled {
  opacity: 0.7;
}

.is-center {
  text-align: center !important;
}

.is-right {
  text-align: right !important;
}

.sp-modules__name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-modules__blocking {
  margin-top: 2px;
  max-width: 320px;
  font-size: 10.5px;
  color: var(--sp-danger);
  white-space: normal;
}

.sp-modules__version {
  color: var(--sp-muted);
  white-space: nowrap;
}

.sp-modules__contributions {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  max-width: 440px;
}

.sp-modules__core {
  padding: 1px 5px;
  border: 1px solid var(--sp-primary-soft-strong);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-primary-soft);
  color: var(--sp-primary);
  font-family: var(--sp-font-mono);
  font-size: 10px;
}

.sp-modules__owner-only {
  font-size: 10px;
}
</style>
