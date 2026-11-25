<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton } from 'element-plus'

import { ApiError, fetchTodos } from '../api/client'
import type { TodoItem, WritePlanCreateResponse } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useContextStore } from '../stores/context'
import { changeOrderIdFromHref } from '../utils/format'
import ChangeOrderCreateDialog from '../components/ChangeOrderCreateDialog.vue'
import PageHeader from '../components/PageHeader.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'
import TodoList from '../components/TodoList.vue'
import TodoTabs from '../components/TodoTabs.vue'

type TabKey = 'all' | 'approval' | 'exception'

const router = useRouter()
const session = useSessionStore()
const context = useContextStore()

const items = ref<TodoItem[]>([])
const loading = ref(true)
const errorText = ref('')
const readonly = ref(true)
const activeTab = ref<TabKey>('all')
const createOpen = ref(false)

const role = computed(() => session.role || context.role)
const canCreate = computed(() => role.value === 'OWNER' || role.value === 'EDITOR')

const counts = computed(() => ({
  all: items.value.length,
  approval: items.value.filter((item) => item.type === 'TODO-APPROVAL' && item.gate_level === 'L2')
    .length,
  exception: items.value.filter((item) => item.type === 'TODO-EXCEPTION').length,
}))

const hint = computed(() =>
  activeTab.value === 'exception' ? zhCN.p05.exceptionHint : zhCN.p05.hint,
)

const filteredItems = computed(() => {
  if (activeTab.value === 'approval') {
    return items.value.filter((item) => item.type === 'TODO-APPROVAL' && item.gate_level === 'L2')
  }
  if (activeTab.value === 'exception') {
    return items.value.filter((item) => item.type === 'TODO-EXCEPTION')
  }
  return items.value
})

async function load(): Promise<void> {
  loading.value = true
  errorText.value = ''
  try {
    const payload = await fetchTodos()
    items.value = payload.items ?? []
    readonly.value = Boolean(payload.readonly)
  } catch (cause) {
    errorText.value =
      cause instanceof ApiError
        ? cause.userMessage
        : cause && typeof cause === 'object' && 'userMessage' in cause
          ? String((cause as { userMessage: unknown }).userMessage)
          : zhCN.p05.loadFailed
  } finally {
    loading.value = false
  }
}

function openTodo(item: TodoItem): void {
  const id = changeOrderIdFromHref(item.href)
  if (!id) return
  void router.push(`/change-orders/${encodeURIComponent(id)}`)
}

function openCreate(): void {
  createOpen.value = true
}

function closeCreate(): void {
  createOpen.value = false
}

async function onCreated(payload: WritePlanCreateResponse): Promise<void> {
  createOpen.value = false
  await load()
  const taskId = payload.task_id
  if (!taskId) return
  void router.push(`/change-orders/${encodeURIComponent(taskId)}`)
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="sp-page sp-p05">
    <PageHeader
      :eyebrow="zhCN.p05.eyebrow"
      :title="zhCN.p05.title"
      :description="zhCN.p05.description"
    >
      <template #meta>
        <span>{{ zhCN.p05.total.replace('{count}', String(items.length)) }}</span>
        <StatusBadge v-if="readonly" :label="zhCN.common.readonlyMode" tone="neutral" />
      </template>
      <template #actions>
        <ElButton
          v-if="canCreate"
          size="small"
          type="primary"
          data-action="create-change-order"
          @click="openCreate"
        >
          {{ zhCN.p05.create.button }}
        </ElButton>
        <ElButton :loading="loading" size="small" @click="load">{{ zhCN.p05.refresh }}</ElButton>
      </template>
    </PageHeader>

    <section class="sp-panel sp-p05__panel">
      <TodoTabs v-model:active="activeTab" :counts="counts" />
      <div class="sp-p05__hint">{{ hint }}</div>
      <div class="sp-p05__body">
        <StateView v-if="loading" state="loading" compact />
        <StateView
          v-else-if="errorText"
          state="error"
          :title="zhCN.p05.loadFailed"
          :description="errorText"
          compact
          @retry="load"
        />
        <TodoList v-else :items="filteredItems" @open="openTodo" />
      </div>
    </section>

    <ChangeOrderCreateDialog
      :open="createOpen"
      @close="closeCreate"
      @created="onCreated"
    />
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p05__panel {
  overflow: hidden;
}

.sp-p05__hint {
  padding: 6px 14px;
  border-bottom: 1px solid var(--sp-border);
  background: var(--sp-surface);
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-p05__body {
  padding: 12px;
  background: var(--sp-bg);
}
</style>
