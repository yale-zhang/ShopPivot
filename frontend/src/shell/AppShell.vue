<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterView } from 'vue-router'

import { zhCN } from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useContextStore } from '../stores/context'
import { useShellStore } from '../stores/shell'
import GlobalContextBar from './GlobalContextBar.vue'
import StatusBar from './StatusBar.vue'
import SideNav from './SideNav.vue'

const context = useContextStore()
const session = useSessionStore()
const shell = useShellStore()

const booting = ref(true)
const bootError = ref('')

async function boot(): Promise<void> {
  booting.value = true
  bootError.value = ''
  try {
    if (context.loaded && context.role && session.role && context.role !== session.role) {
      await context.load(true)
    } else {
      await context.ensureLoaded()
    }
    await Promise.all([shell.loadNav(), shell.refreshStatus()])
  } catch (cause) {
    bootError.value =
      cause && typeof cause === 'object' && 'userMessage' in cause
        ? String((cause as { userMessage: unknown }).userMessage)
        : zhCN.shell.contextLoadFailed
  } finally {
    booting.value = false
  }
}

watch(
  () => [context.platform, context.shopId, context.window, context.metricVersion] as const,
  () => {
    if (!booting.value) void shell.refreshStatus()
  },
)

onMounted(() => {
  void boot()
})
</script>

<template>
  <div class="sp-shell">
    <a class="sp-skip-link" href="#sp-main">{{ zhCN.app.skipToContent }}</a>
    <GlobalContextBar />
    <StatusBar />
    <div v-if="bootError" class="sp-shell__boot-error" role="alert">
      <span>{{ bootError }}</span>
      <button type="button" @click="boot">{{ zhCN.common.retry }}</button>
    </div>
    <div class="sp-shell__body">
      <SideNav />
      <main id="sp-main" class="sp-shell__main" tabindex="-1">
        <div class="sp-shell__content">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.sp-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 100vh;
  background: var(--sp-bg);
  overflow: hidden;
}

.sp-shell__body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.sp-shell__main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background: var(--sp-bg);
  outline: none;
}

.sp-shell__content {
  max-width: var(--sp-content-max);
  margin: 0 auto;
  padding: 18px 22px 36px;
}

.sp-shell__boot-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 18px;
  background: var(--sp-danger-soft);
  border-bottom: 1px solid var(--sp-danger-border);
  color: var(--sp-danger);
  font-size: 11.5px;
}

.sp-shell__boot-error button {
  padding: 1px 8px;
  border: 1px solid var(--sp-danger-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface);
  color: var(--sp-danger);
  font-size: 11px;
}

@media (max-width: 820px) {
  .sp-shell {
    height: auto;
    min-height: 100vh;
    overflow: visible;
  }
  .sp-shell__body {
    flex-direction: column;
  }
  .sp-shell__content {
    padding: 14px 12px 28px;
  }
}
</style>
