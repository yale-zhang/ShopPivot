<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton } from 'element-plus'

import { zhCN } from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'

const router = useRouter()
const route = useRoute()
const session = useSessionStore()

const username = ref('')
const password = ref('')
const localError = ref('')

const errorText = computed(() => localError.value || session.error)

const redirectTarget = computed(() => {
  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) {
    return redirect
  }
  return '/p01'
})

async function onSubmit(): Promise<void> {
  localError.value = ''
  if (!username.value.trim()) {
    localError.value = zhCN.auth.usernameRequired
    return
  }
  if (!password.value) {
    localError.value = zhCN.auth.passwordRequired
    return
  }
  const ok = await session.login(username.value.trim(), password.value)
  if (ok) {
    await router.replace(redirectTarget.value)
  }
}

function clearError(): void {
  localError.value = ''
  session.error = ''
}
</script>

<template>
  <div class="sp-login">
    <section class="sp-login__side">
      <div class="sp-login__brand">
        <span class="sp-login__mark" aria-hidden="true">SP</span>
        <div>
          <div class="sp-login__name">
            {{ zhCN.app.name }}
            <span class="sp-login__latin">{{ zhCN.app.latin }}</span>
          </div>
          <div class="sp-login__tagline">{{ zhCN.app.tagline }}</div>
        </div>
      </div>

      <div class="sp-login__statement">
        <div class="sp-login__milestone">{{ zhCN.app.milestone }}</div>
        <h1 class="sp-login__headline">{{ zhCN.auth.panelTitle }}</h1>
        <p class="sp-login__lead">{{ zhCN.auth.panelLead }}</p>
      </div>

      <ul class="sp-login__points">
        <li class="sp-login__point">
          <span class="sp-login__point-mark" aria-hidden="true">01</span>
          <span>{{ zhCN.auth.points.readonly }}</span>
        </li>
        <li class="sp-login__point">
          <span class="sp-login__point-mark" aria-hidden="true">02</span>
          <span>{{ zhCN.auth.points.drill }}</span>
        </li>
        <li class="sp-login__point">
          <span class="sp-login__point-mark" aria-hidden="true">03</span>
          <span>{{ zhCN.auth.points.evidence }}</span>
        </li>
      </ul>

      <div class="sp-login__foot">{{ zhCN.app.footerNote }}</div>
    </section>

    <section class="sp-login__main">
      <div class="sp-login__card">
        <div class="sp-login__card-head">
          <h2 class="sp-login__title">{{ zhCN.auth.title }}</h2>
          <p class="sp-login__subtitle">{{ zhCN.auth.subtitle }}</p>
        </div>

        <form class="sp-login__form" @submit.prevent="onSubmit">
          <label class="sp-field">
            <span class="sp-field__label">{{ zhCN.auth.username }}</span>
            <input
              v-model="username"
              class="sp-field__input"
              type="text"
              name="username"
              autocomplete="username"
              :placeholder="zhCN.auth.usernamePlaceholder"
              :disabled="session.pending"
              @input="clearError"
            />
          </label>

          <label class="sp-field">
            <span class="sp-field__label">{{ zhCN.auth.password }}</span>
            <input
              v-model="password"
              class="sp-field__input"
              type="password"
              name="password"
              autocomplete="current-password"
              :placeholder="zhCN.auth.passwordPlaceholder"
              :disabled="session.pending"
              @input="clearError"
            />
          </label>

          <p v-if="errorText" class="sp-login__error" role="alert">{{ errorText }}</p>

          <ElButton
            type="primary"
            native-type="submit"
            class="sp-login__submit"
            :loading="session.pending"
            :disabled="session.pending"
          >
            {{ session.pending ? zhCN.auth.submitting : zhCN.auth.submit }}
          </ElButton>
        </form>

        <div class="sp-login__hint">{{ zhCN.auth.hint }}</div>
      </div>

      <p class="sp-login__footer">{{ zhCN.auth.footer }}</p>
    </section>
  </div>
</template>

<style scoped>
.sp-login {
  display: grid;
  grid-template-columns: minmax(380px, 46%) minmax(0, 1fr);
  min-height: 100vh;
  background: var(--sp-bg);
}

.sp-login__side {
  display: flex;
  flex-direction: column;
  gap: 34px;
  padding: 34px 42px;
  background: var(--sp-primary);
  color: #f2f7f8;
  border-right: 1px solid var(--sp-primary-active);
}

.sp-login__brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sp-login__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: var(--sp-radius);
  font-family: var(--sp-font-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #fff;
}

.sp-login__name {
  font-size: 16px;
  font-weight: 650;
  line-height: 1.25;
}

.sp-login__latin {
  margin-left: 5px;
  font-family: var(--sp-font-mono);
  font-size: 10px;
  font-weight: 400;
  color: #aecbd0;
}

.sp-login__tagline {
  font-size: 10.5px;
  color: #aecbd0;
}

.sp-login__statement {
  max-width: 460px;
}

.sp-login__milestone {
  display: inline-block;
  margin-bottom: 10px;
  padding: 2px 7px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: var(--sp-radius-sm);
  font-family: var(--sp-font-mono);
  font-size: 10px;
  color: #d6e6e9;
}

.sp-login__headline {
  font-size: 30px;
  line-height: 1.25;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: #fff;
}

.sp-login__lead {
  margin-top: 10px;
  max-width: 420px;
  font-size: 13px;
  line-height: 1.7;
  color: #c9dee2;
}

.sp-login__points {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-width: 470px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
}

.sp-login__point {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  font-size: 12px;
  line-height: 1.6;
  color: #d6e6e9;
}

.sp-login__point-mark {
  flex: none;
  font-family: var(--sp-font-mono);
  font-size: 10px;
  color: #8fb7be;
  padding-top: 2px;
}

.sp-login__foot {
  margin-top: auto;
  font-family: var(--sp-font-mono);
  font-size: 9.5px;
  color: #8fb7be;
}

.sp-login__main {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
}

.sp-login__card {
  width: min(368px, 100%);
  padding: 24px;
  background: var(--sp-surface);
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  box-shadow: 0 1px 0 rgba(31, 42, 48, 0.03);
}

.sp-login__card-head {
  margin-bottom: 18px;
}

.sp-login__title {
  font-size: 19px;
  font-weight: 650;
  line-height: 1.3;
  color: var(--sp-text);
}

.sp-login__subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--sp-muted);
}

.sp-login__form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sp-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sp-field__label {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-field__input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  font-size: 13px;
  color: var(--sp-text);
  outline: none;
  transition: border-color 120ms ease, box-shadow 120ms ease;
}

.sp-field__input::placeholder {
  color: var(--sp-faint);
}

.sp-field__input:focus {
  border-color: var(--sp-primary);
  box-shadow: var(--sp-focus);
}

.sp-field__input:disabled {
  background: var(--sp-surface-sunken);
  color: var(--sp-faint);
}

.sp-login__error {
  padding: 6px 9px;
  border: 1px solid var(--sp-danger-border);
  border-left: 3px solid var(--sp-danger);
  border-radius: var(--sp-radius-sm);
  background: var(--sp-danger-soft);
  color: var(--sp-danger);
  font-size: 11.5px;
  line-height: 1.5;
}

.sp-login__submit {
  width: 100%;
  height: 34px;
  margin-top: 2px;
}

.sp-login__hint {
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid var(--sp-border);
  font-family: var(--sp-font-mono);
  font-size: 10px;
  color: var(--sp-faint);
}

.sp-login__footer {
  margin-top: 14px;
  font-size: 10.5px;
  color: var(--sp-faint);
}

@media (max-width: 860px) {
  .sp-login {
    grid-template-columns: 1fr;
  }
  .sp-login__side {
    gap: 20px;
    padding: 24px 22px;
    border-right: 0;
    border-bottom: 1px solid var(--sp-primary-active);
  }
  .sp-login__headline {
    font-size: 23px;
  }
  .sp-login__points {
    display: none;
  }
  .sp-login__foot {
    display: none;
  }
  .sp-login__main {
    padding: 26px 16px 40px;
  }
}
</style>
