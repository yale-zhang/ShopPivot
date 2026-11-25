<script setup lang="ts">
import { computed } from 'vue'
import { ElTag } from 'element-plus'

import type { Tone } from '../i18n/zh-CN'
import { labelForStatus, toneForStatus } from '../utils/status'

const props = defineProps<{
  status?: string | null
  label?: string
  tone?: Tone
  title?: string
  dot?: boolean
}>()

const resolvedTone = computed<Tone>(() => props.tone ?? toneForStatus(props.status))
const resolvedLabel = computed(() => props.label ?? labelForStatus(props.status))
</script>

<template>
  <ElTag
    size="small"
    class="sp-status-tag"
    :class="`sp-status-tag--${resolvedTone}`"
    :title="title"
  >
    <span v-if="dot" class="sp-status-tag__dot" aria-hidden="true" />
    {{ resolvedLabel }}
  </ElTag>
</template>

<style scoped>
.sp-status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.sp-status-tag__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  flex: none;
}
</style>
