import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { fetchContexts } from '../api/client'
import type { ShopRef } from '../api/types'

/**
 * 全局上下文（平台 / 店铺 / 时间窗 / 口径版本）。
 * 页面监听这四个值变化后重新请求自己的卡片数据。
 */
export const useContextStore = defineStore('context', () => {
  const platforms = ref<string[]>([])
  const shops = ref<ShopRef[]>([])
  const windows = ref<string[]>([])
  const metricVersions = ref<string[]>([])
  const platform = ref('')
  const shopId = ref('')
  const window = ref('')
  const metricVersion = ref('')
  const role = ref('')
  const readonly = ref(true)
  const platformGateMax = ref('')
  const loading = ref(false)
  const error = ref('')
  let loadPromise: Promise<void> | null = null

  const loaded = computed(() => platforms.value.length > 0)
  const currentShop = computed<ShopRef | null>(
    () => shops.value.find((item) => item.shop_id === shopId.value) ?? null,
  )
  const availableShops = computed<ShopRef[]>(() =>
    shops.value.filter((item) => !platform.value || item.platform === platform.value),
  )

  function pickShop(preferredPlatform: string): void {
    const candidates = shops.value.filter((item) => item.platform === preferredPlatform)
    const current = candidates.find((item) => item.shop_id === shopId.value)
    shopId.value = current?.shop_id ?? candidates[0]?.shop_id ?? shops.value[0]?.shop_id ?? ''
  }

  function setPlatform(next: string): void {
    if (!next || next === platform.value) return
    platform.value = next
    pickShop(next)
  }

  function setShop(next: string): void {
    shopId.value = next
  }

  function setWindow(next: string): void {
    window.value = next
  }

  function setMetricVersion(next: string): void {
    metricVersion.value = next
  }

  async function load(force = false): Promise<void> {
    if (loadPromise && !force) return loadPromise
    loading.value = true
    error.value = ''
    const promise = (async () => {
      try {
        const payload = await fetchContexts()
        platforms.value = payload.platforms ?? []
        shops.value = payload.shops ?? []
        windows.value = payload.windows ?? []
        metricVersions.value = payload.metric_versions ?? []
        role.value = payload.role ?? ''
        readonly.value = Boolean(payload.readonly)
        platformGateMax.value = payload.platform_gate_max ?? ''

        const fallbackPlatform = payload.default?.platform ?? platforms.value[0] ?? ''
        if (!platform.value || !platforms.value.includes(platform.value)) {
          platform.value = fallbackPlatform
        }
        if (!window.value || !windows.value.includes(window.value)) {
          window.value =
            payload.default?.window && windows.value.includes(payload.default.window)
              ? payload.default.window
              : (windows.value[0] ?? '')
        }
        if (!metricVersion.value || !metricVersions.value.includes(metricVersion.value)) {
          metricVersion.value = metricVersions.value[0] ?? ''
        }
        pickShop(platform.value)
      } catch (cause) {
        error.value =
          cause && typeof cause === 'object' && 'userMessage' in cause
            ? String((cause as { userMessage: unknown }).userMessage)
            : ''
        throw cause
      } finally {
        loading.value = false
        loadPromise = null
      }
    })()
    loadPromise = promise
    return promise
  }

  async function ensureLoaded(): Promise<void> {
    if (loaded.value) return
    await load()
  }

  return {
    platforms,
    shops,
    windows,
    metricVersions,
    platform,
    shopId,
    window,
    metricVersion,
    role,
    readonly,
    platformGateMax,
    loading,
    error,
    loaded,
    currentShop,
    availableShops,
    load,
    ensureLoaded,
    setPlatform,
    setShop,
    setWindow,
    setMetricVersion,
  }
})
