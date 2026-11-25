<script setup lang="ts">
import type { BlockedModule } from '../api/types'
import { zhCN } from '../i18n/zh-CN'

defineProps<{
  blocked: BlockedModule[]
}>()
</script>

<template>
  <section v-if="blocked.length" class="sp-blocking" role="alert" :aria-label="zhCN.p09.blockedTitle">
    <div class="sp-blocking__head">
      <span class="sp-blocking__mark" aria-hidden="true">!</span>
      <div>
        <h2 class="sp-blocking__title">{{ zhCN.p09.blockedTitle }}</h2>
        <p class="sp-blocking__hint">{{ zhCN.p09.blockedHint }}</p>
      </div>
    </div>
    <ul class="sp-blocking__list">
      <li v-for="(item, index) in blocked" :key="`${item.module}-${item.check}-${index}`" class="sp-blocking__item">
        <div class="sp-blocking__line">
          {{ zhCN.p09.blockedLine(item.module, item.reason) }}
        </div>
        <div class="sp-blocking__check">
          <span class="sp-mono">{{ item.module }}</span>
          <span class="sp-blocking__sep" aria-hidden="true">/</span>
          {{ zhCN.p09.blockedCheck(item.check) }}
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.sp-blocking {
  padding: 12px 14px;
  background: var(--sp-danger-soft);
  border: 1px solid var(--sp-danger-border);
  border-left: 3px solid var(--sp-danger);
  border-radius: var(--sp-radius);
}

.sp-blocking__head {
  display: flex;
  align-items: flex-start;
  gap: 9px;
}

.sp-blocking__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 17px;
  height: 17px;
  margin-top: 1px;
  border: 1px solid var(--sp-danger);
  border-radius: 50%;
  color: var(--sp-danger);
  font-family: var(--sp-font-mono);
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  flex: none;
}

.sp-blocking__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--sp-danger);
}

.sp-blocking__hint {
  margin-top: 1px;
  font-size: 11.5px;
  color: #7d3d38;
}

.sp-blocking__list {
  margin-top: 9px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sp-blocking__item {
  padding: 7px 9px;
  border: 1px solid var(--sp-danger-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface);
}

.sp-blocking__line {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--sp-danger);
  word-break: break-word;
}

.sp-blocking__check {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 2px;
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-blocking__sep {
  color: var(--sp-faint);
}
</style>
