<script setup lang="ts">
defineProps<{
  eyebrow?: string
  title: string
  description?: string
}>()
</script>

<template>
  <header class="sp-page-header">
    <div class="sp-page-header__main">
      <div v-if="eyebrow" class="sp-page-header__eyebrow">{{ eyebrow }}</div>
      <h1 class="sp-page-header__title">{{ title }}</h1>
      <p v-if="description" class="sp-page-header__description">{{ description }}</p>
      <div v-if="$slots.meta" class="sp-page-header__meta">
        <slot name="meta" />
      </div>
    </div>
    <div v-if="$slots.actions" class="sp-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.sp-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--sp-border);
}

.sp-page-header__main {
  min-width: 0;
}

.sp-page-header__eyebrow {
  font-family: var(--sp-font-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--sp-primary);
  margin-bottom: 3px;
}

.sp-page-header__title {
  font-size: 20px;
  line-height: 1.3;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--sp-text);
}

.sp-page-header__description {
  margin-top: 4px;
  max-width: 760px;
  font-size: 12.5px;
  color: var(--sp-muted);
}

.sp-page-header__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 9px;
  font-size: 12px;
  color: var(--sp-muted);
}

.sp-page-header__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  flex: none;
  padding-top: 2px;
}

@media (max-width: 860px) {
  .sp-page-header {
    flex-direction: column;
    gap: 10px;
  }
  .sp-page-header__actions {
    width: 100%;
  }
}
</style>
