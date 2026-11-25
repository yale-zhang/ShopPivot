import { createApp } from 'vue'
import { createPinia } from 'pinia'

import 'element-plus/dist/index.css'
import './styles/tokens.css'
import './styles/base.css'

import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from './api/client'
import { zhCN } from './i18n/zh-CN'
import { useSessionStore } from './stores/session'
import { useToast } from './composables/useToast'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

const session = useSessionStore(pinia)
const { push } = useToast()

setUnauthorizedHandler(() => {
  session.clear()
  const current = router.currentRoute.value
  if (current.path === '/login') return
  push(zhCN.auth.sessionExpired, 'warning')
  void router.replace({
    path: '/login',
    query: current.fullPath ? { redirect: current.fullPath } : undefined,
  })
})

app.use(router)
app.mount('#app')
