import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  DISPLAY_NAME_KEY,
  ROLE_KEY,
  SHOPS_KEY,
  TOKEN_KEY,
  USERNAME_KEY,
  clearAuthStorage,
  login as loginApi,
} from '../api/client'
import type { LoginResponse, ShopRef } from '../api/types'
import { zhCN } from '../i18n/zh-CN'

function readStorage(key: string): string {
  try {
    return localStorage.getItem(key) ?? ''
  } catch {
    return ''
  }
}

function readShops(): ShopRef[] {
  try {
    const raw = localStorage.getItem(SHOPS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as ShopRef[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* 本地存储不可用时忽略 */
  }
}

export const useSessionStore = defineStore('session', () => {
  const token = ref(readStorage(TOKEN_KEY))
  const role = ref(readStorage(ROLE_KEY))
  const username = ref(readStorage(USERNAME_KEY))
  const displayName = ref(readStorage(DISPLAY_NAME_KEY))
  const shops = ref<ShopRef[]>(readShops())
  const pending = ref(false)
  const error = ref('')

  const isAuthenticated = computed(() => Boolean(token.value))
  const isOwner = computed(() => role.value === 'OWNER')
  const roleLabel = computed(() => zhCN.roles[role.value] ?? role.value)

  function applySession(payload: LoginResponse): void {
    token.value = payload.access_token
    role.value = payload.role
    username.value = payload.username ?? username.value
    displayName.value = payload.display_name ?? ''
    shops.value = payload.shops ?? []
    writeStorage(TOKEN_KEY, token.value)
    writeStorage(ROLE_KEY, role.value)
    writeStorage(USERNAME_KEY, username.value)
    writeStorage(DISPLAY_NAME_KEY, displayName.value)
    writeStorage(SHOPS_KEY, JSON.stringify(shops.value))
  }

  async function login(name: string, password: string): Promise<boolean> {
    pending.value = true
    error.value = ''
    try {
      const payload = await loginApi(name, password)
      username.value = name
      applySession(payload)
      return true
    } catch (cause) {
      const message =
        cause && typeof cause === 'object' && 'userMessage' in cause
          ? String((cause as { userMessage: unknown }).userMessage)
          : zhCN.auth.failed
      error.value = message || zhCN.auth.failed
      return false
    } finally {
      pending.value = false
    }
  }

  function clear(): void {
    token.value = ''
    role.value = ''
    username.value = ''
    displayName.value = ''
    shops.value = []
    error.value = ''
    clearAuthStorage()
  }

  function logout(): void {
    clear()
  }

  return {
    token,
    role,
    username,
    displayName,
    shops,
    pending,
    error,
    isAuthenticated,
    isOwner,
    roleLabel,
    login,
    clear,
    logout,
  }
})
