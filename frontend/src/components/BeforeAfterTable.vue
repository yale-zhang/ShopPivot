<script setup lang="ts">
import type { BeforeAfterRow } from '../api/types'
import { zhCN } from '../i18n/zh-CN'

defineProps<{
  rows: BeforeAfterRow[]
}>()
</script>

<template>
  <div class="sp-before-after">
    <table v-if="rows.length" class="sp-before-after__table">
      <thead>
        <tr>
          <th scope="col">{{ zhCN.p06.table.target }}</th>
          <th scope="col">{{ zhCN.p06.table.field }}</th>
          <th scope="col">{{ zhCN.p06.table.before }}</th>
          <th scope="col">{{ zhCN.p06.table.after }}</th>
          <th scope="col">{{ zhCN.p06.table.impact }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="`${row.target}-${row.field}-${index}`">
          <td class="sp-mono">{{ row.target }}</td>
          <td>{{ row.field }}</td>
          <td><span class="sp-before-after__before">{{ row.before }}</span></td>
          <td><span class="sp-before-after__after">{{ row.after }}</span></td>
          <td class="sp-muted">{{ row.impact }}</td>
        </tr>
      </tbody>
    </table>
    <div v-else class="sp-before-after__empty">{{ zhCN.p06.table.empty }}</div>
  </div>
</template>

<style scoped>
.sp-before-after {
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  overflow: hidden;
}

.sp-before-after__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}

.sp-before-after__table th {
  padding: 7px 10px;
  background: var(--sp-surface-sunken);
  border-bottom: 1px solid var(--sp-border);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--sp-muted);
  text-align: left;
  white-space: nowrap;
}

.sp-before-after__table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--sp-border);
  vertical-align: top;
}

.sp-before-after__table tbody tr:last-child td {
  border-bottom: 0;
}

.sp-before-after__before {
  color: var(--sp-muted);
  font-family: var(--sp-font-mono);
}

.sp-before-after__after {
  color: var(--sp-primary);
  font-family: var(--sp-font-mono);
  font-weight: 600;
}

.sp-before-after__empty {
  padding: 18px;
  text-align: center;
  font-size: 12px;
  color: var(--sp-muted);
  background: var(--sp-surface);
}
</style>
