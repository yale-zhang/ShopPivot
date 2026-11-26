<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'

import type { NavPage } from '../api/types'
import { zhCN } from '../i18n/zh-CN'
import { useShellStore } from '../stores/shell'
import { useToast } from '../composables/useToast'
import StateView from '../components/StateView.vue'

const route = useRoute()
const shell = useShellStore()
const { push } = useToast()

const PAGE_ROUTES: Record<string, string> = {
  P01: '/p01',
  P02: '/p02',
  P03: '/p03',
  P04: '/p04',
  P05: '/p05',
  P06: '/change-orders',
  P07: '/p07',
  P08: '/p08',
  P09: '/p09',
  P10: '/p10',
  P11: '/p11',
  P12: '/p12',
  P13: '/p13',
  P14: '/p14',
}

function routeFor(page: NavPage): string | null {
  if (!page.available) return null
  return PAGE_ROUTES[page.page_id] ?? null
}

function isActive(page: NavPage): boolean {
  const path = routeFor(page)
  if (!path) return false
  return route.path === path || route.path.startsWith(`${path}/`)
}

function onUnavailable(): void {
  push(zhCN.nav.unavailable, 'info')
}
</script>

<template>
  <aside class="sp-sidenav">
    <div class="sp-sidenav__head">
      <span class="sp-sidenav__title">{{ zhCN.nav.brand }}</span>
      <span class="sp-sidenav__stage">{{ zhCN.nav.footer }}</span>
    </div>

    <StateView v-if="shell.navLoading && !shell.pages.length" state="loading" compact />
    <StateView
      v-else-if="shell.navError && !shell.pages.length"
      state="error"
      :title="zhCN.nav.loadFailed"
      :description="shell.navError"
      compact
      @retry="shell.loadNav"
    />

    <nav v-else class="sp-sidenav__nav" :aria-label="zhCN.nav.brand">
      <div v-for="group in shell.groupedPages" :key="group.menu" class="sp-sidenav__group">
        <div class="sp-sidenav__group-label">{{ group.menu }}</div>
        <ul class="sp-sidenav__list">
          <li v-for="page in group.pages" :key="page.page_id">
            <RouterLink
              v-if="routeFor(page)"
              :to="routeFor(page) as string"
              class="sp-sidenav__item"
              :class="{ 'is-active': isActive(page) }"
              :title="page.title"
            >
              <span class="sp-sidenav__page sp-mono">{{ page.page_id }}</span>
              <span class="sp-sidenav__label">{{ page.title }}</span>
            </RouterLink>
            <button
              v-else
              type="button"
              class="sp-sidenav__item is-disabled"
              :title="zhCN.nav.unavailable"
              :aria-disabled="true"
              @click="onUnavailable"
            >
              <span class="sp-sidenav__page sp-mono">{{ page.page_id }}</span>
              <span class="sp-sidenav__label">{{ page.title }}</span>
              <span class="sp-sidenav__pending">{{ zhCN.nav.unavailable }}</span>
            </button>
          </li>
        </ul>
      </div>
    </nav>

    <div class="sp-sidenav__foot">
      <span class="sp-sidenav__foot-label">{{ zhCN.app.footerNote }}</span>
      <span class="sp-sidenav__foot-mark" aria-hidden="true">M1</span>
    </div>
  </aside>
</template>

<style scoped>
.sp-sidenav {
  display: flex;
  flex-direction: column;
  width: var(--sp-nav-width);
  flex: none;
  min-height: 0;
  background: var(--sp-surface);
  border-right: 1px solid var(--sp-border);
  overflow-y: auto;
}

.sp-sidenav__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 11px 14px 9px;
  border-bottom: 1px solid var(--sp-border);
}

.sp-sidenav__title {
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--sp-muted);
}

.sp-sidenav__stage {
  font-family: var(--sp-font-mono);
  font-size: 9.5px;
  color: var(--sp-faint);
}

.sp-sidenav__nav {
  flex: 1;
  padding: 8px 0 12px;
}

.sp-sidenav__group {
  padding: 7px 0 5px;
}

.sp-sidenav__group-label {
  padding: 0 14px 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--sp-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sp-sidenav__list {
  display: flex;
  flex-direction: column;
}

.sp-sidenav__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 28px;
  padding: 4px 14px;
  border: 0;
  border-left: 2px solid transparent;
  background: transparent;
  color: var(--sp-text);
  text-align: left;
  text-decoration: none;
  font-size: 12px;
  line-height: 1.35;
}

.sp-sidenav__item:hover {
  background: var(--sp-surface-sunken);
  color: var(--sp-text);
  text-decoration: none;
}

.sp-sidenav__item.is-active {
  background: var(--sp-primary-soft);
  border-left-color: var(--sp-primary);
  color: var(--sp-primary);
  font-weight: 600;
}

.sp-sidenav__item.is-disabled {
  color: var(--sp-faint);
  cursor: not-allowed;
  padding-top: 5px;
  padding-bottom: 5px;
}

.sp-sidenav__item.is-disabled:hover {
  background: var(--sp-surface-sunken);
}

.sp-sidenav__page {
  flex: none;
  width: 28px;
  font-size: 9.5px;
  color: var(--sp-faint);
}

.sp-sidenav__item.is-active .sp-sidenav__page {
  color: var(--sp-primary);
}

.sp-sidenav__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sp-sidenav__pending {
  display: none;
  position: absolute;
  left: 14px;
  right: 8px;
  top: calc(100% - 2px);
  z-index: 2;
  padding: 3px 5px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-surface);
  box-shadow: var(--el-box-shadow-light);
  color: var(--sp-muted);
  font-size: 9.5px;
  font-weight: 400;
  line-height: 1.35;
  white-space: normal;
}

.sp-sidenav__item.is-disabled:hover .sp-sidenav__pending,
.sp-sidenav__item.is-disabled:focus-visible .sp-sidenav__pending {
  display: block;
}

.sp-sidenav__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  padding: 9px 14px;
  border-top: 1px solid var(--sp-border);
  background: var(--sp-surface-sunken);
}

.sp-sidenav__foot-label {
  font-size: 9px;
  line-height: 1.35;
  color: var(--sp-faint);
}

.sp-sidenav__foot-mark {
  font-family: var(--sp-font-mono);
  font-size: 9px;
  color: var(--sp-faint);
}

@media (max-width: 960px) {
  .sp-sidenav {
    width: 188px;
  }
}
</style>
