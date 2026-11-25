<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElButton } from 'element-plus'

import type { TodoItem } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { formatDateTime } from '../utils/format'
import { labelForStatus, labelForTodoType, toneForStatus, toneForTodoType } from '../utils/status'
import CountdownBadge from './CountdownBadge.vue'
import StateView from './StateView.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  items: TodoItem[]
}>()

const emit = defineEmits<{ (event: 'open', item: TodoItem): void }>()

const syncedAt = ref(Date.now())

watch(
  () => props.items,
  () => {
    syncedAt.value = Date.now()
  },
)

function isApproval(item: TodoItem): boolean {
  return item.type === 'TODO-APPROVAL'
}

function openItem(item: TodoItem): void {
  if (!isApproval(item) || !item.href) return
  emit('open', item)
}

function onKeydown(event: KeyboardEvent, item: TodoItem): void {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    openItem(item)
  }
}
</script>

<template>
  <div v-if="items.length" class="sp-todos">
    <div class="sp-todos__head" aria-hidden="true">
      <span>{{ zhCN.p05.columns.type }}</span>
      <span>{{ zhCN.p05.columns.title }}</span>
      <span>{{ zhCN.p05.columns.status }}</span>
      <span>{{ zhCN.p05.columns.countdown }}</span>
      <span class="is-right">{{ zhCN.p05.columns.action }}</span>
    </div>
    <div
      v-for="item in items"
      :key="item.todo_id"
      class="sp-todos__row"
      :class="{
        'is-approval': isApproval(item),
        'is-overdue': item.overdue && item.status === 'PENDING',
        'is-expired': item.status === 'EXPIRED',
      }"
      :role="isApproval(item) ? 'button' : undefined"
      :tabindex="isApproval(item) ? 0 : undefined"
      @click="openItem(item)"
      @keydown="onKeydown($event, item)"
    >
      <div class="sp-todos__type">
        <StatusBadge
          :label="labelForTodoType(item.type)"
          :tone="toneForTodoType(item.type)"
          dot
        />
        <span class="sp-todos__gate sp-mono">{{ item.gate_level || zhCN.common.none }}</span>
      </div>
      <div class="sp-todos__main">
        <div class="sp-todos__title">{{ item.title }}</div>
        <div class="sp-todos__meta">
          <span>{{ zhCN.p05.module }} · {{ item.module }}</span>
          <span v-if="item.created_at">
            {{ zhCN.p05.createdAt }} {{ formatDateTime(item.created_at) }}
          </span>
          <span v-if="item.sla_expires_at" class="sp-mono">
            {{ zhCN.p05.sla }} {{ formatDateTime(item.sla_expires_at) }}
          </span>
        </div>
      </div>
      <div class="sp-todos__status">
        <StatusBadge :label="labelForStatus(item.status)" :tone="toneForStatus(item.status)" />
      </div>
      <div class="sp-todos__countdown">
        <CountdownBadge
          :remaining-seconds="item.remaining_seconds"
          :status="item.status"
          :overdue="item.overdue"
          :synced-at="syncedAt"
        />
      </div>
      <div class="sp-todos__action">
        <ElButton
          v-if="isApproval(item)"
          size="small"
          :disabled="!item.href"
          @click.stop="openItem(item)"
        >
          {{ zhCN.p05.openChangeOrder }}
        </ElButton>
        <StatusBadge v-else :label="zhCN.common.readonly" tone="neutral" />
      </div>
    </div>
  </div>
  <StateView v-else state="empty" :title="zhCN.p05.empty" :description="zhCN.p05.emptyHint" />
</template>

<style scoped>
.sp-todos {
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  overflow: hidden;
  background: var(--sp-surface);
}

.sp-todos__head,
.sp-todos__row {
  display: grid;
  grid-template-columns: 112px minmax(220px, 1fr) 84px 180px 96px;
  align-items: center;
  gap: 8px;
}

.sp-todos__head {
  padding: 7px 12px;
  background: var(--sp-surface-sunken);
  border-bottom: 1px solid var(--sp-border);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--sp-muted);
}

.sp-todos__head .is-right {
  text-align: right;
}

.sp-todos__row {
  padding: 10px 12px;
  border-bottom: 1px solid var(--sp-border);
  outline: none;
}

.sp-todos__row:last-child {
  border-bottom: 0;
}

.sp-todos__row.is-approval {
  cursor: pointer;
}

.sp-todos__row.is-approval:hover,
.sp-todos__row.is-approval:focus-visible {
  background: #f7fafb;
}

.sp-todos__row.is-overdue {
  box-shadow: inset 3px 0 0 var(--sp-warning);
}

.sp-todos__row.is-expired {
  background: #fafbfb;
  opacity: 0.75;
}

.sp-todos__type {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
}

.sp-todos__gate {
  font-size: 10px;
  color: var(--sp-faint);
}

.sp-todos__main {
  min-width: 0;
}

.sp-todos__title {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--sp-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sp-todos__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 3px 12px;
  margin-top: 2px;
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-todos__status {
  align-self: center;
}

.sp-todos__countdown {
  min-width: 0;
}

.sp-todos__action {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 920px) {
  .sp-todos__head {
    display: none;
  }
  .sp-todos__row {
    grid-template-columns: 120px minmax(0, 1fr);
  }
  .sp-todos__status,
  .sp-todos__countdown,
  .sp-todos__action {
    grid-column: 2;
  }
  .sp-todos__action {
    justify-content: flex-start;
  }
}
</style>
