import { createRouter, createWebHistory } from 'vue-router'

import { getToken } from './api/client'
import { zhCN } from './i18n/zh-CN'
import AppShell from './shell/AppShell.vue'
import LoginPage from './pages/LoginPage.vue'
import P01Dashboard from './pages/P01Dashboard.vue'
import P02Reviews from './pages/P02Reviews.vue'
import P03Inventory from './pages/P03Inventory.vue'
import P04Ads from './pages/P04Ads.vue'
import P05Todos from './pages/P05Todos.vue'
import P06ChangeOrder from './pages/P06ChangeOrder.vue'
import P07Audit from './pages/P07Audit.vue'
import P08Reconciliation from './pages/P08Reconciliation.vue'
import P09Modules from './pages/P09Modules.vue'
import P10MetricCards from './pages/P10MetricCards.vue'
import P11Workers from './pages/P11Workers.vue'
import P12Access from './pages/P12Access.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
      meta: { title: zhCN.auth.title, public: true },
    },
    {
      path: '/',
      component: AppShell,
      children: [
        { path: '', redirect: '/p01' },
        {
          path: 'p01',
          name: 'p01',
          component: P01Dashboard,
          meta: { title: zhCN.p01.title },
        },
        {
          path: 'p02',
          name: 'p02',
          component: P02Reviews,
          meta: { title: zhCN.p02.title },
        },
        {
          path: 'p03',
          name: 'p03',
          component: P03Inventory,
          meta: { title: zhCN.p03.title },
        },
        {
          path: 'p04',
          name: 'p04',
          component: P04Ads,
          meta: { title: zhCN.p04.title },
        },
        {
          path: 'p05',
          name: 'p05',
          component: P05Todos,
          meta: { title: zhCN.p05.title },
        },
        {
          path: 'change-orders',
          name: 'change-orders',
          component: P06ChangeOrder,
          meta: { title: zhCN.p06.title },
        },
        {
          path: 'change-orders/:id',
          name: 'change-order-detail',
          component: P06ChangeOrder,
          meta: { title: zhCN.p06.title },
        },
        {
          path: 'p07',
          name: 'p07',
          component: P07Audit,
          meta: { title: zhCN.p07.title },
        },
        {
          path: 'p08',
          name: 'p08',
          component: P08Reconciliation,
          meta: { title: zhCN.p08.title },
        },
        {
          path: 'p09',
          name: 'p09',
          component: P09Modules,
          meta: { title: zhCN.p09.title },
        },
        {
          path: 'p10',
          name: 'p10',
          component: P10MetricCards,
          meta: { title: zhCN.p10.title },
        },
        {
          path: 'p11',
          name: 'p11',
          component: P11Workers,
          meta: { title: zhCN.p11.title },
        },
        {
          path: 'p12',
          name: 'p12',
          component: P12Access,
          meta: { title: zhCN.p12.title },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/p01' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  const token = getToken()
  if (!token && !to.meta.public) {
    return {
      path: '/login',
      query: to.fullPath && to.fullPath !== '/' ? { redirect: to.fullPath } : undefined,
    }
  }
  if (token && to.name === 'login') {
    return { path: '/p01' }
  }
  return true
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${zhCN.app.name} · ${title}` : zhCN.app.name
})

export default router
