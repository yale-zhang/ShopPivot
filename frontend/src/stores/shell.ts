import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { fetchLatestReport, fetchNav, fetchTodos, fetchWorkers } from '../api/client'
import type { NavPage } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { useContextStore } from './context'

/** 外壳数据：左侧导航 + 顶部状态条。 */
export const useShellStore = defineStore('shell', () => {
  const pages = ref<NavPage[]>([])
  const navLoading = ref(false)
  const navError = ref('')
  const navReadonly = ref(true)

  const runId = ref('')
  const lastCollectedAt = ref('')
  const todoCount = ref(0)
  const workerOnline = ref(0)
  const readonly = ref(true)
  const statusError = ref('')

  const groupedPages = computed(() => {
    const groups: Array<{ menu: string; pages: NavPage[] }> = []
    for (const page of pages.value) {
      const existing = groups.find((group) => group.menu === page.menu)
      if (existing) existing.pages.push(page)
      else groups.push({ menu: page.menu, pages: [page] })
    }
    return groups
  })

  async function loadNav(): Promise<void> {
    navLoading.value = true
    navError.value = ''
    try {
      const payload = await fetchNav()
      pages.value = payload.pages ?? []
      navReadonly.value = Boolean(payload.readonly)
    } catch (cause) {
      navError.value =
        cause && typeof cause === 'object' && 'userMessage' in cause
          ? String((cause as { userMessage: unknown }).userMessage)
          : zhCN.nav.loadFailed
    } finally {
      navLoading.value = false
    }
  }

  async function refreshStatus(): Promise<void> {
    const context = useContextStore()
    try {
      await context.ensureLoaded()
    } catch {
      return
    }
    if (!context.platform || !context.shopId) return
    statusError.value = ''
    const [reportResult, todosResult, workersResult] = await Promise.allSettled([
      fetchLatestReport({
        platform: context.platform,
        shopId: context.shopId,
        window: context.window,
        metricVersion: context.metricVersion,
      }),
      fetchTodos(),
      fetchWorkers(),
    ])

    if (reportResult.status === 'fulfilled') {
      runId.value = reportResult.value.run_id ?? ''
      lastCollectedAt.value = reportResult.value.generated_at ?? ''
    } else {
      runId.value = ''
      lastCollectedAt.value = ''
      statusError.value = zhCN.shell.statusLoadFailed
    }

    if (todosResult.status === 'fulfilled') {
      todoCount.value = Object.values(todosResult.value.counts ?? {}).reduce(
        (sum, value) => sum + Number(value || 0),
        0,
      )
    } else {
      todoCount.value = 0
      statusError.value = zhCN.shell.statusLoadFailed
    }

    if (workersResult.status === 'fulfilled') {
      workerOnline.value = workersResult.value.online ?? 0
    } else {
      workerOnline.value = 0
      statusError.value = zhCN.shell.statusLoadFailed
    }

    readonly.value = context.readonly
  }

  function resetStatus(): void {
    runId.value = ''
    lastCollectedAt.value = ''
    todoCount.value = 0
    workerOnline.value = 0
    statusError.value = ''
  }

  return {
    pages,
    navLoading,
    navError,
    navReadonly,
    groupedPages,
    runId,
    lastCollectedAt,
    todoCount,
    workerOnline,
    readonly,
    statusError,
    loadNav,
    refreshStatus,
    resetStatus,
  }
})
