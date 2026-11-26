<script setup lang="ts">
import { ElTable, ElTableColumn } from 'element-plus'

import type { SkillRun } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { formatDateTime } from '../utils/format'
import { toneForStatus } from '../utils/status'
import StateView from './StateView.vue'
import StatusBadge from './StatusBadge.vue'

withDefaults(
  defineProps<{
    runs: SkillRun[]
    emptyCopy: string
    emptyHint?: string
  }>(),
  { emptyHint: '' },
)

function runStatusLabel(status: string): string {
  return zhCN.p14.runStatusLabels[status] ?? status
}

function latencyText(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return zhCN.common.none
  }
  return zhCN.p14.latencyValue(Number(value))
}
</script>

<template>
  <StateView
    v-if="!runs.length"
    state="empty"
    :title="emptyCopy"
    :description="emptyHint"
    compact
  />
  <ElTable
    v-else
    :data="runs"
    size="small"
    border
    row-key="run_id"
    style="width: 100%"
  >
    <ElTableColumn :label="zhCN.p14.runColumns.createdAt" width="150">
      <template #default="{ row }">
        <span class="sp-mono sp-p14-runs__time">
          {{ formatDateTime(row.created_at) || zhCN.common.none }}
        </span>
      </template>
    </ElTableColumn>
    <ElTableColumn :label="zhCN.p14.runColumns.skill" min-width="164">
      <template #default="{ row }">
        <div class="sp-p14-runs__skill">
          <span class="sp-mono" :data-run-skill="row.skill_id">{{ row.skill_id }}</span>
          <span class="sp-faint sp-p14-runs__version">
            {{ row.skill_version ? `v${row.skill_version}` : zhCN.common.none }}
          </span>
        </div>
      </template>
    </ElTableColumn>
    <ElTableColumn :label="zhCN.p14.runColumns.capability" min-width="150">
      <template #default="{ row }">
        <span class="sp-mono">{{ row.capability || zhCN.common.none }}</span>
      </template>
    </ElTableColumn>
    <ElTableColumn :label="zhCN.p14.runColumns.scene" width="82">
      <template #default="{ row }">
        <span class="sp-mono">{{ row.scene || zhCN.common.none }}</span>
      </template>
    </ElTableColumn>
    <ElTableColumn :label="zhCN.p14.runColumns.platform" min-width="150">
      <template #default="{ row }">
        <span class="sp-mono sp-p14-runs__platform">
          {{ row.platform || zhCN.common.none }} / {{ row.shop_id || zhCN.common.none }}
        </span>
      </template>
    </ElTableColumn>
    <ElTableColumn :label="zhCN.p14.runColumns.status" width="96">
      <template #default="{ row }">
        <StatusBadge :label="runStatusLabel(row.status)" :tone="toneForStatus(row.status)" />
      </template>
    </ElTableColumn>
    <ElTableColumn :label="zhCN.p14.runColumns.latency" width="90" align="right">
      <template #default="{ row }">
        <span class="sp-mono" :class="{ 'sp-faint': row.latency_ms === null }">
          {{ latencyText(row.latency_ms) }}
        </span>
      </template>
    </ElTableColumn>
    <ElTableColumn :label="zhCN.p14.runColumns.errorCode" min-width="124">
      <template #default="{ row }">
        <span v-if="row.error_code" class="sp-mono sp-p14-runs__error">{{ row.error_code }}</span>
        <span v-else class="sp-faint">{{ zhCN.common.none }}</span>
      </template>
    </ElTableColumn>
  </ElTable>
</template>

<style scoped>
.sp-p14-runs__time {
  font-size: 10.5px;
  color: var(--sp-muted);
  white-space: nowrap;
}

.sp-p14-runs__skill {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.sp-p14-runs__skill .sp-mono {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sp-p14-runs__version {
  font-size: 10px;
  white-space: nowrap;
}

.sp-p14-runs__platform {
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-p14-runs__error {
  font-size: 10.5px;
  color: var(--sp-danger);
}
</style>
