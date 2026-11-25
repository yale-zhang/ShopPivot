<script setup lang="ts">
import { ref } from 'vue'
import { ElButton } from 'element-plus'

import { exportReport } from '../api/client'
import { zhCN } from '../i18n/zh-CN'
import { useToast } from '../composables/useToast'

const props = defineProps<{
  reportId: string | null
  watermark?: string
}>()

const { push } = useToast()
const exporting = ref(false)

function triggerDownload(blob: Blob, filename: string): void {
  if (typeof URL.createObjectURL !== 'function') return
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(href), 0)
}

async function onExport(): Promise<void> {
  if (!props.reportId || exporting.value) return
  exporting.value = true
  try {
    const { blob, filename } = await exportReport(props.reportId)
    triggerDownload(blob, filename)
    push(zhCN.p01.exportDone.replace('{filename}', filename), 'success')
  } catch (cause) {
    const message =
      cause && typeof cause === 'object' && 'userMessage' in cause
        ? String((cause as { userMessage: unknown }).userMessage)
        : zhCN.p01.exportFailed
    push(message || zhCN.p01.exportFailed, 'danger')
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="sp-export">
    <span class="sp-export__watermark" :title="watermark || zhCN.p01.exportWatermark">
      <span class="sp-export__watermark-label">{{ zhCN.p01.exportWatermark }}</span>
      <span class="sp-export__watermark-value">{{ watermark || zhCN.common.none }}</span>
    </span>
    <ElButton
      type="primary"
      size="small"
      :loading="exporting"
      :disabled="!reportId || exporting"
      :title="reportId ? zhCN.p01.export : zhCN.p01.exportNoReport"
      @click="onExport"
    >
      {{ exporting ? zhCN.p01.exporting : zhCN.p01.export }}
    </ElButton>
  </div>
</template>

<style scoped>
.sp-export {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.sp-export__watermark {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  max-width: min(360px, 38vw);
  padding: 2px 7px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface-sunken);
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-export__watermark-label {
  flex: none;
  color: var(--sp-faint);
}

.sp-export__watermark-value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--sp-font-mono);
}
</style>
