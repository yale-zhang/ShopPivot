<script setup lang="ts">
import { zhCN } from '../i18n/zh-CN'
import { useToast } from '../composables/useToast'

const { items, dismiss } = useToast()
</script>

<template>
  <div class="sp-toast-host" role="status" aria-live="polite">
    <div
      v-for="item in items"
      :key="item.id"
      class="sp-toast"
      :class="`sp-toast--${item.tone}`"
    >
      <span class="sp-toast__dot" aria-hidden="true" />
      <span class="sp-toast__text">{{ item.message }}</span>
      <button class="sp-toast__close" type="button" :aria-label="zhCN.common.close" @click="dismiss(item.id)">
        ×
      </button>
    </div>
  </div>
</template>

<style scoped>
.sp-toast-host {
  position: fixed;
  top: 68px;
  right: 18px;
  z-index: 4000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(360px, calc(100vw - 32px));
  pointer-events: none;
}

.sp-toast {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  background: var(--sp-surface);
  border: 1px solid var(--sp-border);
  border-left: 3px solid var(--sp-info);
  border-radius: var(--sp-radius);
  box-shadow: 0 6px 20px rgba(31, 42, 48, 0.12);
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--sp-text);
  pointer-events: auto;
}

.sp-toast--success { border-left-color: var(--sp-success); }
.sp-toast--warning { border-left-color: var(--sp-warning); }
.sp-toast--danger { border-left-color: var(--sp-danger); }
.sp-toast--primary { border-left-color: var(--sp-primary); }

.sp-toast__dot {
  width: 6px;
  height: 6px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--sp-info);
  flex: none;
}
.sp-toast--success .sp-toast__dot { background: var(--sp-success); }
.sp-toast--warning .sp-toast__dot { background: var(--sp-warning); }
.sp-toast--danger .sp-toast__dot { background: var(--sp-danger); }
.sp-toast--primary .sp-toast__dot { background: var(--sp-primary); }

.sp-toast__text {
  flex: 1;
  word-break: break-word;
}

.sp-toast__close {
  flex: none;
  border: 0;
  background: transparent;
  color: var(--sp-muted);
  font-size: 14px;
  line-height: 1;
  padding: 2px;
  cursor: pointer;
}
.sp-toast__close:hover { color: var(--sp-text); }
</style>
