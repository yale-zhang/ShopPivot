<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElOption, ElSelect } from 'element-plus'

import { zhCN } from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useContextStore } from '../stores/context'
import { useShellStore } from '../stores/shell'
import StatusBadge from '../components/StatusBadge.vue'

const router = useRouter()
const context = useContextStore()
const session = useSessionStore()
const shell = useShellStore()

const roleText = computed(() => {
  const code = session.role || context.role
  if (!code) return zhCN.common.none
  const label = zhCN.roles[code] ?? code
  return label === code ? code : `${label} · ${code}`
})

const displayUser = computed(() => session.displayName || session.username || zhCN.common.none)

const notificationLabel = computed(
  () => `${zhCN.common.notifications} ${shell.todoCount} ${zhCN.common.unread}`,
)

function onPlatform(value: string): void {
  context.setPlatform(String(value))
}

function onShop(value: string): void {
  context.setShop(String(value))
}

function onWindow(value: string): void {
  context.setWindow(String(value))
}

function onMetricVersion(value: string): void {
  context.setMetricVersion(String(value))
}

function openNotifications(): void {
  void router.push('/p05')
}

function logout(): void {
  session.logout()
  void router.replace('/login')
}
</script>

<template>
  <header class="sp-global-bar">
    <div class="sp-brand">
      <span class="sp-brand__mark" aria-hidden="true">SP</span>
      <div class="sp-brand__text">
        <div class="sp-brand__name">
          {{ zhCN.app.name }}
          <span class="sp-brand__latin">{{ zhCN.app.latin }}</span>
        </div>
        <div class="sp-brand__meta">{{ zhCN.app.tagline }} · {{ zhCN.app.milestone }}</div>
      </div>
    </div>

    <div class="sp-context" :aria-label="zhCN.context.title">
      <label class="sp-context__field">
        <span class="sp-context__label">{{ zhCN.context.platform }}</span>
        <ElSelect
          :model-value="context.platform"
          size="small"
          class="sp-context__select sp-context__select--platform"
          :disabled="!context.loaded || context.loading"
          @update:model-value="onPlatform"
        >
          <ElOption v-for="platform in context.platforms" :key="platform" :label="platform" :value="platform" />
        </ElSelect>
      </label>

      <label class="sp-context__field">
        <span class="sp-context__label">{{ zhCN.context.shop }}</span>
        <ElSelect
          :model-value="context.shopId"
          size="small"
          class="sp-context__select sp-context__select--shop"
          :disabled="!context.loaded || context.loading"
          @update:model-value="onShop"
        >
          <ElOption
            v-for="shop in context.availableShops"
            :key="`${shop.platform}-${shop.shop_id}`"
            :label="shop.shop_id"
            :value="shop.shop_id"
          />
        </ElSelect>
      </label>

      <label class="sp-context__field">
        <span class="sp-context__label">{{ zhCN.context.window }}</span>
        <ElSelect
          :model-value="context.window"
          size="small"
          class="sp-context__select sp-context__select--window"
          :disabled="!context.loaded || context.loading"
          @update:model-value="onWindow"
        >
          <ElOption v-for="item in context.windows" :key="item" :label="item" :value="item" />
        </ElSelect>
      </label>

      <label class="sp-context__field">
        <span class="sp-context__label">{{ zhCN.context.metricVersion }}</span>
        <ElSelect
          :model-value="context.metricVersion"
          size="small"
          class="sp-context__select sp-context__select--version"
          :disabled="!context.loaded || context.loading"
          @update:model-value="onMetricVersion"
        >
          <ElOption
            v-for="item in context.metricVersions"
            :key="item"
            :label="item"
            :value="item"
          />
        </ElSelect>
      </label>
    </div>

    <div class="sp-global-actions">
      <div class="sp-role" :title="displayUser">
        <span class="sp-role__label">{{ zhCN.context.role }}</span>
        <StatusBadge :label="roleText" tone="primary" />
      </div>
      <button
        type="button"
        class="sp-notify"
        :aria-label="notificationLabel"
        :title="notificationLabel"
        @click="openNotifications"
      >
        <span class="sp-notify__label">{{ zhCN.common.notifications }}</span>
        <span class="sp-notify__count">{{ shell.todoCount }}</span>
      </button>
      <span class="sp-user" :title="displayUser">{{ displayUser }}</span>
      <button type="button" class="sp-logout" @click="logout">{{ zhCN.common.logout }}</button>
    </div>
  </header>
</template>

<style scoped>
.sp-global-bar {
  display: flex;
  align-items: center;
  gap: 18px;
  height: var(--sp-header-height);
  padding: 0 18px;
  background: var(--sp-surface);
  border-bottom: 1px solid var(--sp-border);
}

.sp-brand {
  display: flex;
  align-items: center;
  gap: 9px;
  flex: none;
}

.sp-brand__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--sp-radius);
  background: var(--sp-primary);
  color: #fff;
  font-family: var(--sp-font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.sp-brand__name {
  font-size: 14px;
  font-weight: 650;
  line-height: 1.2;
  color: var(--sp-text);
  white-space: nowrap;
}

.sp-brand__latin {
  margin-left: 5px;
  font-family: var(--sp-font-mono);
  font-size: 10px;
  font-weight: 500;
  color: var(--sp-muted);
  letter-spacing: 0.02em;
}

.sp-brand__meta {
  font-size: 9.5px;
  line-height: 1.3;
  color: var(--sp-faint);
  white-space: nowrap;
}

.sp-context {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.sp-context__field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.sp-context__label {
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--sp-faint);
}

.sp-context__select {
  width: 112px;
}

.sp-context__select--platform {
  width: 104px;
}
.sp-context__select--window {
  width: 116px;
}
.sp-context__select--version {
  width: 92px;
}

.sp-global-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: none;
}

.sp-role {
  display: flex;
  align-items: center;
  gap: 5px;
}

.sp-role__label {
  font-size: 10px;
  color: var(--sp-faint);
}

.sp-notify {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 8px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  color: var(--sp-muted);
  font-size: 11px;
}
.sp-notify:hover {
  border-color: var(--sp-primary);
  color: var(--sp-primary);
}

.sp-notify__count {
  min-width: 16px;
  padding: 0 4px;
  border-radius: var(--sp-radius-pill);
  background: var(--sp-primary-soft);
  color: var(--sp-primary);
  font-family: var(--sp-font-mono);
  font-size: 10px;
  line-height: 15px;
  text-align: center;
}

.sp-user {
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11.5px;
  color: var(--sp-muted);
}

.sp-logout {
  height: 26px;
  padding: 0 7px;
  border: 1px solid transparent;
  border-radius: var(--sp-radius);
  background: transparent;
  color: var(--sp-muted);
  font-size: 11px;
}
.sp-logout:hover {
  border-color: var(--sp-border);
  background: var(--sp-surface-sunken);
  color: var(--sp-text);
}

@media (max-width: 1240px) {
  .sp-brand__meta,
  .sp-user,
  .sp-role__label {
    display: none;
  }
  .sp-context {
    gap: 8px;
  }
}

@media (max-width: 1020px) {
  .sp-brand__text {
    display: none;
  }
  .sp-context__label {
    display: none;
  }
  .sp-context__select,
  .sp-context__select--platform,
  .sp-context__select--window,
  .sp-context__select--version {
    width: 96px;
  }
}

@media (max-width: 820px) {
  .sp-global-bar {
    height: auto;
    flex-wrap: wrap;
    gap: 8px 12px;
    padding: 8px 12px;
  }
  .sp-context {
    order: 3;
    width: 100%;
    flex-wrap: wrap;
  }
  .sp-global-actions {
    margin-left: auto;
  }
}
</style>
