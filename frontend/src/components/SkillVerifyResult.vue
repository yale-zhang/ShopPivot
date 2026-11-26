<script setup lang="ts">
/** 校验结果：展示 ok / expected / actual；未通过时整块红色。 */
import { computed } from 'vue'

import type { SkillVerifyResponse } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{ result: SkillVerifyResponse }>()

const ok = computed(() => props.result.ok === true)
</script>

<template>
  <div class="sp-verify" :class="{ 'sp-verify--danger': !ok }" :data-verify-ok="ok ? 'true' : 'false'">
    <div class="sp-verify__head">
      <span class="sp-verify__title">{{ zhCN.p14.verify.title }}</span>
      <StatusBadge
        :label="ok ? zhCN.p14.verify.okLabel : zhCN.p14.verify.failedLabel"
        :tone="ok ? 'success' : 'danger'"
      />
      <span class="sp-verify__skill sp-mono">{{ result.skill_id }}</span>
      <span class="sp-verify__ok sp-mono">{{ zhCN.p14.verify.okValue(ok) }}</span>
    </div>
    <dl class="sp-verify__kv">
      <dt>{{ zhCN.p14.verify.expected }}</dt>
      <dd class="sp-mono">{{ result.expected || zhCN.common.none }}</dd>
      <dt>{{ zhCN.p14.verify.actual }}</dt>
      <dd class="sp-mono">{{ result.actual || zhCN.common.none }}</dd>
    </dl>
    <p class="sp-verify__hint">{{ zhCN.p14.verify.hint }}</p>
  </div>
</template>

<style scoped>
.sp-verify {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 9px 11px;
  border: 1px solid var(--sp-success-border);
  border-left: 3px solid var(--sp-success);
  border-radius: var(--sp-radius);
  background: var(--sp-success-soft);
}

.sp-verify--danger {
  border-color: var(--sp-danger-border);
  border-left-color: var(--sp-danger);
  background: var(--sp-danger-soft);
}

.sp-verify--danger .sp-verify__title {
  color: var(--sp-danger);
}

.sp-verify--danger .sp-verify__kv dd {
  color: var(--sp-danger);
}

.sp-verify__head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.sp-verify__title {
  font-size: 11.5px;
  font-weight: 650;
  color: var(--sp-success);
}

.sp-verify__skill,
.sp-verify__ok {
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-verify__kv {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  gap: 3px 10px;
  margin: 0;
  font-size: 10.5px;
}

.sp-verify__kv dt {
  color: var(--sp-faint);
}

.sp-verify__kv dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
  color: var(--sp-text);
}

.sp-verify__hint {
  font-size: 10px;
  line-height: 1.5;
  color: var(--sp-faint);
}
</style>
