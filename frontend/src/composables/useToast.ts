import { reactive } from 'vue'

import type { Tone } from '../i18n/zh-CN'

export interface ToastItem {
  id: number
  message: string
  tone: Tone
}

const items = reactive<ToastItem[]>([])
let sequence = 0

export function pushToast(message: string, tone: Tone = 'info', timeout = 3600): number {
  const id = ++sequence
  items.push({ id, message, tone })
  if (typeof window !== 'undefined' && timeout > 0) {
    window.setTimeout(() => dismissToast(id), timeout)
  }
  return id
}

export function dismissToast(id: number): void {
  const index = items.findIndex((item) => item.id === id)
  if (index >= 0) items.splice(index, 1)
}

export function useToast() {
  return { items, push: pushToast, dismiss: dismissToast }
}
