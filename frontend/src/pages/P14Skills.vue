<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElButton, ElTable, ElTableColumn } from 'element-plus'

import {
  ApiError,
  deleteSkillBinding,
  disableSkill,
  enableSkill,
  fetchSkillBindings,
  fetchSkillCatalog,
  fetchSkillDetail,
  fetchSkillRuns,
  installSkill,
  putSkillBinding,
  verifySkill,
} from '../api/client'
import type {
  SkillBinding,
  SkillCapability,
  SkillCatalogResponse,
  SkillDetailResponse,
  SkillInstallation,
  SkillInstallPayload,
  SkillInstallSource,
  SkillManifestItem,
  SkillRun,
  SkillRunsResponse,
  SkillVerifyResponse,
} from '../api/types'
import {
  EMPTY_SKILL_RUNS_COPY,
  EMPTY_SKILLS_COPY,
  zhCN,
  type Tone,
} from '../i18n/zh-CN'
import { useSessionStore } from '../stores/session'
import { useToast } from '../composables/useToast'
import { formatDateTime, prettyJson } from '../utils/format'
import { toneForStatus } from '../utils/status'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import DrawerPanel from '../components/DrawerPanel.vue'
import KpiTile from '../components/KpiTile.vue'
import PageHeader from '../components/PageHeader.vue'
import SkillRunTable from '../components/SkillRunTable.vue'
import SkillVerifyResult from '../components/SkillVerifyResult.vue'
import StateView from '../components/StateView.vue'
import StatusBadge from '../components/StatusBadge.vue'

interface KpiItem {
  code: string
  label: string
  value: string
  unit: string
  tone: Tone
}

interface ManifestBlock {
  label: string
  value: string
}

interface InstallationRow {
  label: string
  value: string
  mono?: boolean
}

/** 治理动作：安装 / 校验 走接口，启用 / 停用 需二次确认。 */
type SkillActionKind = 'install' | 'verify' | 'enable' | 'disable'
type ConfirmActionKind = 'install' | 'enable' | 'disable'

interface ConfirmConfig {
  title: string
  body: string
  confirmLabel: string
  success: (skillId: string) => string
  failed: string
  danger: boolean
}

const TRUST_TONES: Record<string, Tone> = {
  official: 'primary',
  verified: 'success',
  community: 'warning',
  untrusted: 'danger',
}

const STATUS_TONES: Record<string, Tone> = {
  'adapter-only': 'neutral',
  INSTALLED: 'info',
  ENABLED: 'success',
  DISABLED: 'neutral',
  BLOCKED: 'danger',
}

const session = useSessionStore()
const { push } = useToast()

const catalog = ref<SkillCatalogResponse | null>(null)
const loading = ref(true)
const errorText = ref('')
const forbidden = ref(false)

const runs = ref<SkillRunsResponse | null>(null)
const runsLoading = ref(true)
const runsError = ref('')
const selectedSkillId = ref('')

const drawerOpen = ref(false)
const target = ref<SkillManifestItem | null>(null)
const detail = ref<SkillDetailResponse | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

const bindings = ref<SkillBinding[]>([])
const bindingsLoading = ref(false)
const bindingsError = ref('')
const bindingSaving = ref(false)
const bindingDeleting = ref('')
const bindingError = ref('')
const bindingForm = reactive({
  platform: '*',
  shop_id: '*',
  priority: 10,
  credential_ref: '',
  enabled: true,
})

const verifyResult = ref<SkillVerifyResponse | null>(null)
const actionError = ref('')
const busyKey = ref('')
const installationNotes = ref<Record<string, string>>({})

const confirmOpen = ref(false)
const confirmKind = ref<ConfirmActionKind>('install')
const confirmSkill = ref<SkillManifestItem | null>(null)
const dialogError = ref('')
const actionPending = ref(false)
/** 安装弹窗：默认清单安装；选择安装包时必须填写受控目录下的 zip 路径。 */
const installSource = ref<SkillInstallSource>('manifest')
const installPackagePath = ref('')

let catalogSeq = 0
let runsSeq = 0
let detailSeq = 0

const isOwner = computed(() => (session.role || '').toUpperCase() === 'OWNER')

const skills = computed<SkillManifestItem[]>(() => catalog.value?.items ?? [])
const runItems = computed<SkillRun[]>(() => runs.value?.items ?? [])
const filteredRuns = computed<SkillRun[]>(() => {
  if (!selectedSkillId.value) return runItems.value
  return runItems.value.filter((run) => run.skill_id === selectedSkillId.value)
})

const lockPath = computed(() => catalog.value?.lock_path || zhCN.common.none)
const emptyCopy = computed(() => catalog.value?.empty_copy || EMPTY_SKILLS_COPY)
const runsEmptyCopy = computed(() => runs.value?.empty_copy || EMPTY_SKILL_RUNS_COPY)

const drawerManifest = computed<SkillManifestItem | null>(() => detail.value ?? target.value)
const drawerStatus = computed(
  () => detail.value?.status ?? target.value?.status ?? '',
)
const drawerBindings = computed<SkillBinding[]>(() => bindings.value)
const drawerRuns = computed<SkillRun[]>(() => detail.value?.runs ?? [])
const drawerInstallation = computed<SkillInstallation | null>(
  () => detail.value?.installation ?? target.value?.installation ?? null,
)
const drawerInstallNote = computed(() => {
  const skillId = drawerManifest.value?.id ?? ''
  return installationNotes.value[skillId] || drawerInstallation.value?.note || ''
})
const drawerActions = computed<SkillActionKind[]>(() => actionsFor(drawerStatus.value))
const drawerInstalledAt = computed(() =>
  formatDateTime(
    drawerInstallation.value?.installed_at ?? drawerManifest.value?.installed_at ?? '',
  ),
)

const trustedCount = computed(
  () =>
    skills.value.filter((skill) => skill.trust === 'official' || skill.trust === 'verified')
      .length,
)

const capabilityCount = computed(() =>
  skills.value.reduce((sum, skill) => sum + (skill.capabilities?.length ?? 0), 0),
)

/** 运行失败数只从 `/skills/runs` 的状态计算，不推测。 */
const failedRunCount = computed(
  () => runItems.value.filter((run) => (run.status ?? '').toUpperCase() === 'FAILED').length,
)

const kpis = computed<KpiItem[]>(() => [
  {
    code: 'SKILLS',
    label: zhCN.p14.kpi.skills,
    value: String(catalog.value?.count ?? skills.value.length),
    unit: '',
    tone: 'primary',
  },
  {
    code: 'TRUSTED',
    label: zhCN.p14.kpi.trusted,
    value: String(trustedCount.value),
    unit: '',
    tone: 'success',
  },
  {
    code: 'CAPS',
    label: zhCN.p14.kpi.capabilities,
    value: String(capabilityCount.value),
    unit: '',
    tone: 'info',
  },
  {
    code: 'FAILED',
    label: zhCN.p14.kpi.failedRuns,
    value: String(failedRunCount.value),
    unit: '',
    tone: failedRunCount.value > 0 ? 'danger' : 'neutral',
  },
])

const manifestBlocks = computed<ManifestBlock[]>(() => {
  const manifest = drawerManifest.value
  if (!manifest) return []
  return [
    { label: zhCN.p14.drawer.entrypoints, value: prettyJson(manifest.entrypoints ?? {}) },
    { label: zhCN.p14.drawer.limits, value: prettyJson(manifest.limits ?? {}) },
    { label: zhCN.p14.drawer.config, value: prettyJson(manifest.config ?? {}) },
  ]
})

const installationRows = computed<InstallationRow[]>(() => {
  const installation = drawerInstallation.value
  if (!installation) return []
  const rows: InstallationRow[] = [
    {
      label: zhCN.p14.installation.columns.version,
      value: installation.version || zhCN.common.none,
      mono: true,
    },
    {
      label: zhCN.p14.installation.columns.checksum,
      value: installation.checksum || zhCN.common.none,
      mono: true,
    },
    {
      label: zhCN.p14.installation.columns.manifestPath,
      value: installation.manifest_path || zhCN.common.none,
      mono: true,
    },
    {
      label: zhCN.p14.installation.columns.installedBy,
      value: installation.installed_by || zhCN.common.none,
    },
    {
      label: zhCN.p14.installation.columns.installedAt,
      value: formatDateTime(installation.installed_at) || zhCN.common.none,
    },
  ]
  // 安装包安装回填 details：存在时才展示安装方式、包校验和与落盘路径。
  const kind = installDetailText(installation, 'kind')
  if (kind) {
    const kindLabel = zhCN.p14.install.kindLabels[kind]
    rows.push({
      label: zhCN.p14.installation.columns.kind,
      value: kindLabel ? `${kindLabel}（${kind}）` : kind,
    })
  }
  const packageChecksum = installDetailText(installation, 'package_checksum')
  if (packageChecksum) {
    rows.push({
      label: zhCN.p14.installation.columns.packageChecksum,
      value: packageChecksum,
      mono: true,
    })
  }
  const packagePath = installDetailText(installation, 'package_path')
  if (packagePath) {
    rows.push({
      label: zhCN.p14.installation.columns.packagePath,
      value: packagePath,
      mono: true,
    })
  }
  const note = drawerInstallNote.value
  if (note) rows.push({ label: zhCN.p14.installation.columns.note, value: note })
  return rows
})

const confirmConfig = computed<ConfirmConfig>(() => {
  const skillId = confirmSkill.value?.id ?? ''
  if (confirmKind.value === 'enable') {
    return {
      title: zhCN.p14.actions.enableTitle,
      body: zhCN.p14.actions.enableBody(skillId),
      confirmLabel: zhCN.p14.actions.enableConfirm,
      success: zhCN.p14.actions.enableSuccess,
      failed: zhCN.p14.actions.enableFailed,
      danger: false,
    }
  }
  if (confirmKind.value === 'disable') {
    return {
      title: zhCN.p14.actions.disableTitle,
      body: zhCN.p14.actions.disableBody(skillId),
      confirmLabel: zhCN.p14.actions.disableConfirm,
      success: zhCN.p14.actions.disableSuccess,
      failed: zhCN.p14.actions.disableFailed,
      danger: true,
    }
  }
  return {
    title: zhCN.p14.actions.installTitle,
    body: zhCN.p14.actions.installBody(skillId),
    confirmLabel: zhCN.p14.actions.installConfirm,
    success: zhCN.p14.actions.installSuccess,
    failed: zhCN.p14.actions.installFailed,
    danger: false,
  }
})

function normalizeStatusKey(status: string | null | undefined): string {
  const raw = (status ?? '').trim()
  if (!raw) return 'adapter-only'
  if (raw.toLowerCase() === 'adapter-only') return 'adapter-only'
  return raw.toUpperCase()
}

function trustLabel(trust: string): string {
  return zhCN.p14.trustLabels[trust] ?? trust
}

function trustTone(trust: string): Tone {
  return TRUST_TONES[trust] ?? 'neutral'
}

function statusLabel(status: string): string {
  const key = normalizeStatusKey(status)
  return zhCN.p14.statusLabels[key] ?? zhCN.p14.statusLabels[status] ?? status
}

function statusToneFor(status: string): Tone {
  return STATUS_TONES[normalizeStatusKey(status)] ?? toneForStatus(status)
}

function statusHint(status: string): string {
  return zhCN.p14.statusHints[normalizeStatusKey(status)] ?? ''
}

/** 状态 → 可用动作；未知/阻断状态没有动作。 */
function actionsFor(status: string | null | undefined): SkillActionKind[] {
  const key = normalizeStatusKey(status)
  if (key === 'adapter-only') return ['install']
  if (key === 'INSTALLED') return ['verify', 'enable']
  if (key === 'ENABLED') return ['verify', 'disable']
  if (key === 'DISABLED') return ['enable']
  return []
}

function actionLabel(action: SkillActionKind): string {
  return zhCN.p14.actions[action]
}

function isBusy(action: SkillActionKind, skillId: string): boolean {
  return busyKey.value === `${action}:${skillId}`
}

function bindingKey(row: unknown): string {
  const binding = row as SkillBinding
  return `${binding.platform}/${binding.shop_id}`
}

function riskLabel(capability: SkillCapability): string {
  return zhCN.p14.riskLabels[capability.risk] ?? capability.risk_label ?? capability.risk
}

function errorMessage(cause: unknown, fallback: string): string {
  // 后端 message 是原始业务原因（如 409 校验和不匹配），优先原样展示。
  if (cause instanceof ApiError) return cause.message || cause.userMessage || fallback
  if (cause && typeof cause === 'object') {
    if ('message' in cause && typeof cause.message === 'string' && cause.message) {
      return cause.message
    }
    if ('userMessage' in cause) {
      const message = String((cause as { userMessage: unknown }).userMessage)
      if (message) return message
    }
  }
  return fallback
}

/** 安装记录 details 只按字符串读取；缺失或非字符串视为不存在。 */
function installDetailText(
  installation: SkillInstallation,
  key: 'kind' | 'package_checksum' | 'package_path',
): string {
  const value = installation.details?.[key]
  return typeof value === 'string' ? value.trim() : ''
}

function resetInstallForm(): void {
  installSource.value = 'manifest'
  installPackagePath.value = ''
}

function syncTarget(): void {
  if (!target.value) return
  const row = skills.value.find((skill) => skill.id === target.value?.id)
  if (row) target.value = row
}

async function loadCatalog(silent = false): Promise<void> {
  const seq = ++catalogSeq
  if (!silent) {
    loading.value = true
    errorText.value = ''
    forbidden.value = false
  }
  try {
    const response = await fetchSkillCatalog()
    if (seq !== catalogSeq) return
    catalog.value = response
    syncTarget()
  } catch (cause) {
    if (seq !== catalogSeq) return
    if (cause instanceof ApiError && cause.status === 403) {
      if (silent) return
      catalog.value = null
      forbidden.value = true
      return
    }
    if (silent) return
    errorText.value = errorMessage(cause, zhCN.p14.loadFailed)
  } finally {
    if (seq === catalogSeq && !silent) loading.value = false
  }
}

async function loadRuns(silent = false): Promise<void> {
  const seq = ++runsSeq
  if (!silent) {
    runsLoading.value = true
    runsError.value = ''
  }
  try {
    const response = await fetchSkillRuns({ limit: 50 })
    if (seq !== runsSeq) return
    runs.value = response
  } catch (cause) {
    if (seq !== runsSeq) return
    if (silent) return
    runsError.value = errorMessage(cause, zhCN.p14.runsLoadFailed)
  } finally {
    if (seq === runsSeq && !silent) runsLoading.value = false
  }
}

function refreshAll(): void {
  void loadCatalog()
  void loadRuns()
}

function applyDetail(response: SkillDetailResponse): void {
  detail.value = response
  bindings.value = [...(response.bindings ?? [])]
  if (response.installation?.note) {
    installationNotes.value[response.id] = response.installation.note
  }
}

async function loadDetail(skillId: string, silent = false): Promise<void> {
  const seq = ++detailSeq
  if (!silent) {
    detail.value = null
    detailError.value = ''
    detailLoading.value = true
  }
  try {
    const response = await fetchSkillDetail(skillId)
    if (seq !== detailSeq) return
    applyDetail(response)
  } catch (cause) {
    if (seq !== detailSeq) return
    if (silent) return
    if (cause instanceof ApiError && cause.status === 403) {
      detailError.value = zhCN.p14.drawer.detailForbidden
      return
    }
    detailError.value = errorMessage(cause, zhCN.p14.drawer.detailFailed)
  } finally {
    if (seq === detailSeq && !silent) detailLoading.value = false
  }
}

async function loadBindings(skillId: string): Promise<void> {
  bindingsLoading.value = true
  bindingsError.value = ''
  try {
    const response = await fetchSkillBindings(skillId)
    if (target.value?.id !== skillId) return
    bindings.value = [...(response.items ?? [])]
  } catch (cause) {
    if (target.value?.id !== skillId) return
    bindingsError.value = errorMessage(cause, zhCN.p14.bindings.refreshFailed)
  } finally {
    bindingsLoading.value = false
  }
}

function resetBindingForm(): void {
  bindingForm.platform = '*'
  bindingForm.shop_id = '*'
  bindingForm.priority = 10
  bindingForm.credential_ref = ''
  bindingForm.enabled = true
  bindingError.value = ''
}

function upsertBinding(binding: SkillBinding): void {
  const key = bindingKey(binding)
  const index = bindings.value.findIndex((item) => bindingKey(item) === key)
  if (index >= 0) {
    bindings.value = bindings.value.map((item, current) =>
      current === index ? binding : item,
    )
    return
  }
  bindings.value = [...bindings.value, binding]
}

/** 治理动作成功后刷新目录、运行记录与（抽屉中的）详情。 */
async function refreshSkillData(skillId?: string): Promise<void> {
  await Promise.all([loadCatalog(true), loadRuns(true)])
  const drawerSkillId = target.value?.id ?? ''
  if (drawerSkillId && (!skillId || drawerSkillId === skillId)) {
    await loadDetail(drawerSkillId, true)
    syncTarget()
  }
}

function openSkill(row: unknown): void {
  const skill = row as SkillManifestItem
  if (!skill?.id) return
  target.value = skill
  drawerOpen.value = true
  bindings.value = [...(skill.bindings ?? [])]
  bindingsError.value = ''
  resetBindingForm()
  void loadDetail(skill.id)
}

function retryDetail(): void {
  const skill = target.value
  if (!skill) return
  void loadDetail(skill.id)
}

function closeDrawer(): void {
  detailSeq += 1
  drawerOpen.value = false
  target.value = null
  detail.value = null
  detailError.value = ''
  detailLoading.value = false
  bindings.value = []
  bindingsError.value = ''
  bindingError.value = ''
  bindingDeleting.value = ''
}

function askAction(action: SkillActionKind, row: unknown): void {
  const skill = row as SkillManifestItem
  if (!isOwner.value) {
    push(zhCN.p14.actions.noPermission, 'warning')
    return
  }
  if (busyKey.value || actionPending.value) return
  if (action === 'verify') {
    void runVerify(skill)
    return
  }
  confirmKind.value = action
  confirmSkill.value = skill
  dialogError.value = ''
  actionError.value = ''
  resetInstallForm()
  confirmOpen.value = true
}

function cancelConfirm(): void {
  if (actionPending.value) return
  confirmOpen.value = false
  confirmSkill.value = null
  dialogError.value = ''
  resetInstallForm()
}

async function runVerify(skill: SkillManifestItem): Promise<void> {
  if (!isOwner.value || busyKey.value) return
  busyKey.value = `verify:${skill.id}`
  actionError.value = ''
  try {
    const result = await verifySkill(skill.id)
    verifyResult.value = result
    push(
      result.ok
        ? zhCN.p14.actions.verifySuccess(skill.id)
        : zhCN.p14.actions.verifyMismatch(skill.id),
      result.ok ? 'success' : 'danger',
    )
    await refreshSkillData(skill.id)
  } catch (cause) {
    const message = errorMessage(cause, zhCN.p14.actions.verifyFailed)
    actionError.value = message
    push(message, 'danger')
  } finally {
    busyKey.value = ''
  }
}

async function confirmAction(): Promise<void> {
  const skill = confirmSkill.value
  if (!skill) return
  const kind = confirmKind.value
  const config = confirmConfig.value
  dialogError.value = ''
  actionError.value = ''
  // 安装包必须先填路径：校验不通过时不发请求，只在弹窗内提示。
  let installPayload: SkillInstallPayload | null = null
  if (kind === 'install' && installSource.value === 'package') {
    const packagePath = installPackagePath.value.trim()
    if (!packagePath) {
      dialogError.value = zhCN.p14.install.packageRequired
      return
    }
    installPayload = { source: 'package', package_path: packagePath }
  }
  actionPending.value = true
  busyKey.value = `${kind}:${skill.id}`
  try {
    let installation: SkillInstallation | null = null
    if (kind === 'install') {
      installation = installPayload
        ? await installSkill(skill.id, installPayload)
        : await installSkill(skill.id)
    } else if (kind === 'enable') installation = await enableSkill(skill.id)
    else installation = await disableSkill(skill.id)
    if (installation?.note) installationNotes.value[skill.id] = installation.note
    push(config.success(skill.id), 'success')
    confirmOpen.value = false
    confirmSkill.value = null
    resetInstallForm()
    await refreshSkillData(skill.id)
  } catch (cause) {
    const message = errorMessage(cause, config.failed)
    dialogError.value = message
    actionError.value = message
    push(message, 'danger')
  } finally {
    actionPending.value = false
    busyKey.value = ''
  }
}

async function saveBinding(): Promise<void> {
  const skill = target.value
  if (!skill || !isOwner.value || bindingSaving.value) return
  const platform = bindingForm.platform.trim() || '*'
  const shopId = bindingForm.shop_id.trim() || '*'
  const priority = Number(bindingForm.priority)
  if (!Number.isInteger(priority) || priority < 0 || priority > 1000) {
    bindingError.value = zhCN.p14.bindings.priorityInvalid
    return
  }
  bindingSaving.value = true
  bindingError.value = ''
  try {
    const saved = await putSkillBinding(skill.id, {
      platform,
      shop_id: shopId,
      enabled: bindingForm.enabled,
      priority,
      credential_ref: bindingForm.credential_ref.trim(),
      config: {},
    })
    upsertBinding({
      ...saved,
      platform: saved.platform || platform,
      shop_id: saved.shop_id || shopId,
    })
    push(zhCN.p14.bindings.saveSuccess(platform, shopId), 'success')
    resetBindingForm()
    await loadBindings(skill.id)
    await loadCatalog(true)
  } catch (cause) {
    const message = errorMessage(cause, zhCN.p14.bindings.saveFailed)
    bindingError.value = message
    push(message, 'danger')
  } finally {
    bindingSaving.value = false
  }
}

async function removeBinding(row: unknown): Promise<void> {
  const skill = target.value
  if (!skill || !isOwner.value || bindingDeleting.value) return
  const binding = row as SkillBinding
  const key = bindingKey(binding)
  bindingDeleting.value = key
  bindingError.value = ''
  try {
    await deleteSkillBinding(skill.id, binding.platform, binding.shop_id)
    bindings.value = bindings.value.filter((item) => bindingKey(item) !== key)
    push(zhCN.p14.bindings.deleteSuccess(binding.platform, binding.shop_id), 'success')
    await loadBindings(skill.id)
    await loadCatalog(true)
  } catch (cause) {
    const message = errorMessage(cause, zhCN.p14.bindings.deleteFailed)
    bindingError.value = message
    push(message, 'danger')
  } finally {
    bindingDeleting.value = ''
  }
}

onMounted(() => {
  void loadCatalog()
  void loadRuns()
})
</script>

<template>
  <div class="sp-page sp-p14">
    <PageHeader
      :eyebrow="zhCN.p14.eyebrow"
      :title="zhCN.p14.title"
      :description="zhCN.p14.description"
    >
      <template #meta>
        <StatusBadge
          :label="isOwner ? zhCN.p14.ownerBadge : zhCN.p14.viewerBadge"
          :tone="isOwner ? 'primary' : 'neutral'"
        />
        <span v-if="catalog">
          <span class="sp-faint">{{ zhCN.p14.totalLabel }}</span>
          <span class="sp-p14__meta sp-mono">{{ skills.length }}</span>
        </span>
        <span v-if="catalog">
          <span class="sp-faint">{{ zhCN.p14.lockPath }}</span>
          <span class="sp-p14__meta sp-mono">{{ lockPath }}</span>
        </span>
      </template>
      <template #actions>
        <ElButton size="small" :loading="loading || runsLoading" @click="refreshAll">
          {{ zhCN.p14.refresh }}
        </ElButton>
      </template>
    </PageHeader>

    <section class="sp-p14__readonly" role="note" data-p14="readonly-note">
      <span class="sp-p14__readonly-label">{{ zhCN.p14.readonlyLabel }}</span>
      <span class="sp-p14__readonly-text">{{ zhCN.p14.readonlyNote }}</span>
      <span class="sp-p14__lock">
        <span class="sp-faint">{{ zhCN.p14.lockPath }}</span>
        <code class="sp-mono" data-p14="lock-path">{{ lockPath }}</code>
        <span class="sp-p14__lock-hint">{{ zhCN.p14.lockPathHint }}</span>
        <span v-if="!isOwner" class="sp-p14__lock-hint" data-p14="readonly-role-hint">
          {{ zhCN.p14.ownerOnlyHint }}
        </span>
      </span>
    </section>

    <StateView v-if="loading" state="loading" compact />
    <StateView
      v-else-if="forbidden"
      state="forbidden"
      :title="zhCN.p14.forbidden"
      :description="zhCN.p14.forbiddenHint"
      :retryable="false"
      compact
    />
    <StateView
      v-else-if="errorText"
      state="error"
      :title="zhCN.p14.loadFailed"
      :description="errorText"
      compact
      @retry="loadCatalog()"
    />

    <template v-else>
      <section class="sp-p14__kpis" data-p14="kpis" :aria-label="zhCN.p14.title">
        <KpiTile
          v-for="item in kpis"
          :key="item.code"
          :label="item.label"
          :value="item.value"
          :unit="item.unit"
          :code="item.code"
          :tone="item.tone"
        />
      </section>

      <section
        v-if="verifyResult"
        class="sp-p14__verify-wrap"
        data-p14="verify-result"
        role="status"
      >
        <SkillVerifyResult :result="verifyResult" />
      </section>

      <section
        v-if="actionError"
        class="sp-p14__action-error"
        data-p14="action-error"
        role="alert"
      >
        {{ actionError }}
      </section>

      <section class="sp-panel sp-p14__skills" data-p14="skills">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p14.tableTitle }}</span>
            <span v-if="skills.length" class="sp-panel__count">{{ skills.length }}</span>
          </div>
          <span class="sp-panel__hint">{{ zhCN.p14.tableHint }}</span>
        </div>

        <StateView
          v-if="!skills.length"
          state="empty"
          :title="emptyCopy"
          :description="zhCN.p14.emptyHint"
          compact
        />
        <ElTable
          v-else
          :data="skills"
          size="small"
          border
          row-key="id"
          style="width: 100%"
          @row-click="openSkill"
        >
          <ElTableColumn :label="zhCN.p14.columns.id" min-width="196">
            <template #default="{ row }">
              <button
                type="button"
                class="sp-link-btn sp-mono"
                data-open="skill"
                :data-skill-id="row.id"
                :aria-label="zhCN.p14.openRow"
                @click.stop="openSkill(row)"
              >
                {{ row.id }}
              </button>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p14.columns.version" width="96">
            <template #default="{ row }">
              <span class="sp-mono">v{{ row.version }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p14.columns.publisher" min-width="126">
            <template #default="{ row }">
              <span class="sp-p14__publisher" :title="row.publisher">
                {{ row.publisher || zhCN.common.none }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p14.columns.trust" width="100">
            <template #default="{ row }">
              <span :data-trust="row.trust">
                <StatusBadge :label="trustLabel(row.trust)" :tone="trustTone(row.trust)" />
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p14.columns.license" width="104">
            <template #default="{ row }">
              <span class="sp-mono">{{ row.license || zhCN.common.none }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p14.columns.status" width="108">
            <template #default="{ row }">
              <span
                :data-skill-status="normalizeStatusKey(row.status)"
                :title="statusHint(row.status)"
              >
                <StatusBadge :label="statusLabel(row.status)" :tone="statusToneFor(row.status)" />
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p14.columns.capabilities" min-width="290">
            <template #default="{ row }">
              <div v-if="row.capabilities.length" class="sp-p14__caps">
                <span
                  v-for="capability in row.capabilities"
                  :key="capability.name"
                  class="sp-chip sp-p14__cap"
                >
                  <span class="sp-mono">{{ capability.name }}</span>
                  <span
                    class="sp-p14__risk"
                    :class="`sp-p14__risk--${capability.risk.toLowerCase()}`"
                  >
                    <span class="sp-mono">{{ capability.risk }}</span>
                    {{ riskLabel(capability) }}
                  </span>
                </span>
              </div>
              <span v-else class="sp-faint">{{ zhCN.p14.noCapabilities }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn :label="zhCN.p14.columns.bindings" width="88" align="right">
            <template #default="{ row }">
              <span class="sp-mono" :title="zhCN.p14.bindingCount(row.bindings.length)">
                {{ row.bindings.length }}
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn
            v-if="isOwner"
            :label="zhCN.p14.columns.actions"
            width="168"
            align="right"
          >
            <template #default="{ row }">
              <div class="sp-p14__row-actions">
                <ElButton
                  v-for="action in actionsFor(row.status)"
                  :key="action"
                  link
                  size="small"
                  :type="action === 'disable' ? 'danger' : 'primary'"
                  :loading="isBusy(action, row.id)"
                  :disabled="Boolean(busyKey) && !isBusy(action, row.id)"
                  :data-skill-action="action"
                  :data-skill-action-id="row.id"
                  :aria-label="`${actionLabel(action)} ${row.id}`"
                  @click.stop="askAction(action, row)"
                >
                  {{ actionLabel(action) }}
                </ElButton>
              </div>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>

      <section class="sp-panel sp-p14__runs" data-p14="runs">
        <div class="sp-panel__header">
          <div class="sp-panel__title">
            <span>{{ zhCN.p14.runsTitle }}</span>
            <span v-if="runItems.length" class="sp-panel__count">{{ runItems.length }}</span>
          </div>
          <div class="sp-p14__runs-tools">
            <label class="sp-p14__filter">
              <span class="sp-p14__filter-label">{{ zhCN.p14.runsFilter }}</span>
              <select v-model="selectedSkillId" class="sp-p14__control" data-filter="skill">
                <option value="">{{ zhCN.p14.allSkills }}</option>
                <option v-for="skill in skills" :key="skill.id" :value="skill.id">
                  {{ skill.id }}
                </option>
              </select>
            </label>
            <span class="sp-panel__hint">{{ zhCN.p14.runsHint }}</span>
          </div>
        </div>

        <StateView v-if="runsLoading" state="loading" compact />
        <StateView
          v-else-if="runsError"
          state="error"
          :title="zhCN.p14.runsLoadFailed"
          :description="runsError"
          compact
          @retry="loadRuns()"
        />
        <SkillRunTable
          v-else
          :runs="filteredRuns"
          :empty-copy="runItems.length ? zhCN.p14.runsEmptyFiltered : runsEmptyCopy"
          :empty-hint="runItems.length ? '' : zhCN.p14.runsEmptyHint"
        />
      </section>
    </template>

    <DrawerPanel
      :open="drawerOpen"
      :title="zhCN.p14.drawer.title"
      :subtitle="target ? target.id : zhCN.p14.drawer.subtitle"
      width="720px"
      :close-label="zhCN.p14.drawer.close"
      @close="closeDrawer"
    >
      <div v-if="target" class="sp-p14__detail" data-p14="drawer">
        <div class="sp-p14__detail-head">
          <span class="sp-mono sp-p14__detail-id">{{ target.id }}</span>
          <span class="sp-mono sp-faint">v{{ target.version }}</span>
          <StatusBadge :label="trustLabel(target.trust)" :tone="trustTone(target.trust)" />
          <StatusBadge
            :label="statusLabel(drawerStatus)"
            :tone="statusToneFor(drawerStatus)"
          />
        </div>

        <section v-if="isOwner" class="sp-p14__sub" data-p14="drawer-actions">
          <h3>{{ zhCN.p14.drawer.governance }}</h3>
          <p class="sp-p14__hint">{{ zhCN.p14.drawer.governanceHint }}</p>
          <div class="sp-p14__row-actions sp-p14__row-actions--start">
            <ElButton
              v-for="action in drawerActions"
              :key="action"
              size="small"
              :type="action === 'disable' ? 'danger' : 'primary'"
              plain
              :loading="isBusy(action, target.id)"
              :disabled="Boolean(busyKey) && !isBusy(action, target.id)"
              :data-drawer-action="action"
              :data-skill-action-id="target.id"
              @click.stop="askAction(action, target)"
            >
              {{ actionLabel(action) }}
            </ElButton>
            <span v-if="!drawerActions.length" class="sp-faint">
              {{ zhCN.p14.actions.noActions }}
            </span>
          </div>
        </section>

        <section
          v-if="verifyResult && verifyResult.skill_id === target.id"
          class="sp-p14__sub"
          data-p14="drawer-verify"
        >
          <h3>{{ zhCN.p14.verify.title }}</h3>
          <SkillVerifyResult :result="verifyResult" />
        </section>

        <section class="sp-p14__sub">
          <h3>{{ zhCN.p14.drawer.summary }}</h3>
          <p class="sp-p14__desc">
            {{ drawerManifest?.description || zhCN.p14.drawer.noDescription }}
          </p>
          <dl class="sp-p14__kv">
            <dt>{{ zhCN.p14.drawer.adapter }}</dt>
            <dd class="sp-mono">{{ drawerManifest?.adapter || zhCN.common.none }}</dd>
            <dt>{{ zhCN.p14.drawer.publisher }}</dt>
            <dd>{{ drawerManifest?.publisher || zhCN.common.none }}</dd>
            <dt>{{ zhCN.p14.drawer.version }}</dt>
            <dd class="sp-mono">{{ drawerManifest?.version || zhCN.common.none }}</dd>
            <dt>{{ zhCN.p14.drawer.trust }}</dt>
            <dd>
              <StatusBadge
                :label="trustLabel(drawerManifest?.trust ?? '')"
                :tone="trustTone(drawerManifest?.trust ?? '')"
              />
            </dd>
            <dt>{{ zhCN.p14.drawer.license }}</dt>
            <dd class="sp-mono">{{ drawerManifest?.license || zhCN.common.none }}</dd>
            <dt>{{ zhCN.p14.drawer.checksum }}</dt>
            <dd class="sp-mono">{{ drawerManifest?.checksum || zhCN.common.none }}</dd>
          </dl>
        </section>

        <section class="sp-p14__sub" data-p14="drawer-installation">
          <h3>{{ zhCN.p14.installation.title }}</h3>
          <p class="sp-p14__hint">{{ zhCN.p14.installation.hint }}</p>
          <template v-if="drawerInstallation">
            <div class="sp-p14__install-head">
              <StatusBadge
                :label="statusLabel(drawerInstallation.status)"
                :tone="statusToneFor(drawerInstallation.status)"
              />
            </div>
            <dl class="sp-p14__kv" data-p14="installation-detail">
              <template v-for="row in installationRows" :key="row.label">
                <dt>{{ row.label }}</dt>
                <dd :class="{ 'sp-mono': row.mono }">{{ row.value }}</dd>
              </template>
            </dl>
          </template>
          <p v-else-if="drawerInstalledAt" class="sp-p14__hint">
            {{ zhCN.p14.installation.columns.installedAt }} · {{ drawerInstalledAt }}
          </p>
          <p v-else class="sp-faint">{{ zhCN.p14.installation.empty }}</p>
        </section>

        <section class="sp-p14__sub">
          <h3>{{ zhCN.p14.drawer.capabilities }}</h3>
          <p class="sp-p14__hint">{{ zhCN.p14.drawer.capabilitiesHint }}</p>
          <ul v-if="drawerManifest?.capabilities.length" class="sp-p14__cap-list">
            <li
              v-for="capability in drawerManifest.capabilities"
              :key="capability.name"
              class="sp-p14__cap-item"
            >
              <div class="sp-p14__cap-head">
                <span class="sp-mono">{{ capability.name }}</span>
                <span
                  class="sp-chip sp-p14__risk"
                  :class="`sp-p14__risk--${capability.risk.toLowerCase()}`"
                >
                  <span class="sp-mono">{{ capability.risk }}</span>
                  {{ riskLabel(capability) }}
                </span>
              </div>
              <p v-if="capability.description" class="sp-p14__cap-desc">
                {{ capability.description }}
              </p>
            </li>
          </ul>
          <p v-else class="sp-faint">{{ zhCN.p14.noCapabilities }}</p>
        </section>

        <section class="sp-p14__sub">
          <h3>{{ zhCN.p14.drawer.manifest }}</h3>
          <p class="sp-p14__hint">{{ zhCN.p14.drawer.manifestHint }}</p>
          <div
            v-for="block in manifestBlocks"
            :key="block.label"
            class="sp-p14__code-block"
          >
            <div class="sp-p14__code-label">{{ block.label }}</div>
            <pre class="sp-p14__pre sp-mono">{{ block.value }}</pre>
          </div>
        </section>

        <section class="sp-p14__sub">
          <h3>{{ zhCN.p14.drawer.credentials }}</h3>
          <p class="sp-p14__hint">{{ zhCN.p14.drawer.credentialsHint }}</p>
          <p v-if="drawerManifest?.credentials.length" class="sp-p14__hint">
            {{ zhCN.p14.drawer.credentialsKeysHint }}
          </p>
          <div v-if="drawerManifest?.credentials.length" class="sp-p14__keys">
            <span
              v-for="key in drawerManifest.credentials"
              :key="key"
              class="sp-chip sp-mono"
            >
              {{ key }}
            </span>
          </div>
          <p v-else class="sp-faint">{{ zhCN.p14.drawer.noCredentials }}</p>
        </section>

        <section class="sp-p14__sub" data-p14="drawer-bindings">
          <h3>{{ zhCN.p14.bindings.title }}</h3>
          <p class="sp-p14__hint">{{ zhCN.p14.bindings.hint }}</p>
          <ElTable
            v-if="drawerBindings.length"
            :data="drawerBindings"
            size="small"
            border
            :row-key="bindingKey"
            style="width: 100%"
          >
            <ElTableColumn :label="zhCN.p14.drawer.bindingColumns.platform" min-width="96">
              <template #default="{ row }">
                <span class="sp-mono">{{ row.platform || zhCN.common.none }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn :label="zhCN.p14.drawer.bindingColumns.shopId" min-width="112">
              <template #default="{ row }">
                <span class="sp-mono">{{ row.shop_id || zhCN.common.none }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn :label="zhCN.p14.drawer.bindingColumns.enabled" width="96">
              <template #default="{ row }">
                <StatusBadge
                  :label="
                    row.enabled
                      ? zhCN.p14.drawer.bindingEnabled
                      : zhCN.p14.drawer.bindingDisabled
                  "
                  :tone="row.enabled ? 'success' : 'neutral'"
                />
              </template>
            </ElTableColumn>
            <ElTableColumn :label="zhCN.p14.drawer.bindingColumns.priority" width="80" align="right">
              <template #default="{ row }">
                <span class="sp-mono">{{ row.priority }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn :label="zhCN.p14.drawer.bindingColumns.credentialRef" min-width="150">
              <template #default="{ row }">
                <span v-if="row.credential_ref" class="sp-mono sp-p14__break">
                  {{ row.credential_ref }}
                </span>
                <span v-else class="sp-faint">{{ zhCN.p14.bindings.noCredential }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn
              v-if="isOwner"
              :label="zhCN.p14.drawer.bindingColumns.actions"
              width="72"
              align="right"
            >
              <template #default="{ row }">
                <ElButton
                  link
                  size="small"
                  type="danger"
                  :loading="bindingDeleting === bindingKey(row)"
                  :disabled="Boolean(bindingDeleting)"
                  :data-binding-delete="bindingKey(row)"
                  @click.stop="removeBinding(row)"
                >
                  {{ zhCN.p14.bindings.delete }}
                </ElButton>
              </template>
            </ElTableColumn>
          </ElTable>
          <p v-else class="sp-p14__empty-line">{{ zhCN.p14.drawer.noBindings }}</p>
          <p v-if="bindingsError" class="sp-p14__binding-error" role="alert">
            {{ bindingsError }}
          </p>
          <p v-if="bindingsLoading" class="sp-p14__hint">{{ zhCN.common.refreshing }}</p>

          <form
            v-if="isOwner"
            class="sp-p14__binding-form"
            data-p14="binding-form"
            @submit.prevent="saveBinding"
          >
            <div class="sp-p14__binding-form-head">
              <h4>{{ zhCN.p14.bindings.formTitle }}</h4>
              <span class="sp-p14__hint">{{ zhCN.p14.bindings.hint }}</span>
            </div>
            <div class="sp-p14__binding-grid">
              <label class="sp-p14__field">
                <span class="sp-p14__field-label">{{ zhCN.p14.bindings.columns.platform }}</span>
                <input
                  v-model="bindingForm.platform"
                  class="sp-p14__field-control sp-mono"
                  type="text"
                  :placeholder="zhCN.p14.bindings.platformPlaceholder"
                  :disabled="bindingSaving"
                  data-binding-field="platform"
                />
              </label>
              <label class="sp-p14__field">
                <span class="sp-p14__field-label">{{ zhCN.p14.bindings.columns.shopId }}</span>
                <input
                  v-model="bindingForm.shop_id"
                  class="sp-p14__field-control sp-mono"
                  type="text"
                  :placeholder="zhCN.p14.bindings.shopPlaceholder"
                  :disabled="bindingSaving"
                  data-binding-field="shop_id"
                />
              </label>
              <label class="sp-p14__field">
                <span class="sp-p14__field-label">{{ zhCN.p14.bindings.columns.priority }}</span>
                <input
                  v-model.number="bindingForm.priority"
                  class="sp-p14__field-control sp-mono"
                  type="number"
                  min="0"
                  max="1000"
                  step="1"
                  :disabled="bindingSaving"
                  data-binding-field="priority"
                />
                <span class="sp-p14__field-hint">{{ zhCN.p14.bindings.priorityHint }}</span>
              </label>
              <label class="sp-p14__field">
                <span class="sp-p14__field-label">
                  {{ zhCN.p14.bindings.columns.credentialRef }}
                </span>
                <input
                  v-model="bindingForm.credential_ref"
                  class="sp-p14__field-control sp-mono"
                  type="text"
                  :placeholder="zhCN.p14.bindings.credentialPlaceholder"
                  :disabled="bindingSaving"
                  data-binding-field="credential_ref"
                />
              </label>
              <label class="sp-p14__field sp-p14__field--check">
                <input
                  v-model="bindingForm.enabled"
                  type="checkbox"
                  :disabled="bindingSaving"
                  data-binding-field="enabled"
                />
                <span>{{ zhCN.p14.bindings.enabledLabel }}</span>
              </label>
            </div>
            <p class="sp-p14__hint">{{ zhCN.p14.bindings.credentialHint }}</p>
            <p
              v-if="bindingError"
              class="sp-p14__binding-error"
              data-p14="binding-error"
              role="alert"
            >
              {{ bindingError }}
            </p>
            <div class="sp-p14__binding-actions">
              <ElButton
                size="small"
                type="primary"
                :loading="bindingSaving"
                :disabled="bindingSaving"
                data-binding-save
                @click="saveBinding"
              >
                {{ bindingSaving ? zhCN.p14.bindings.saving : zhCN.p14.bindings.save }}
              </ElButton>
            </div>
          </form>
        </section>

        <section class="sp-p14__sub" data-p14="drawer-runs">
          <h3>{{ zhCN.p14.drawer.runs }}</h3>
          <StateView v-if="detailLoading" state="loading" compact />
          <StateView
            v-else-if="detailError"
            state="error"
            :title="zhCN.p14.drawer.detailFailed"
            :description="detailError"
            compact
            @retry="retryDetail"
          />
          <SkillRunTable
            v-else
            :runs="drawerRuns"
            :empty-copy="zhCN.p14.drawer.runsEmpty"
            :empty-hint="zhCN.p14.drawer.runsEmptyHint"
          />
        </section>
      </div>
    </DrawerPanel>

    <ConfirmDialog
      :open="confirmOpen"
      :title="confirmConfig.title"
      :confirm-label="confirmConfig.confirmLabel"
      :cancel-label="zhCN.common.cancel"
      :danger="confirmConfig.danger"
      :pending="actionPending"
      @confirm="confirmAction"
      @cancel="cancelConfirm"
    >
      <p>{{ confirmConfig.body }}</p>
      <div v-if="confirmKind === 'install'" class="sp-p14__install-form" data-p14="install-form">
        <div
          class="sp-p14__install-sources"
          role="radiogroup"
          :aria-label="zhCN.p14.install.sourceLabel"
        >
          <label class="sp-p14__field--check">
            <input
              v-model="installSource"
              type="radio"
              value="manifest"
              :disabled="actionPending"
              data-install-source="manifest"
            />
            <span>{{ zhCN.p14.install.manifestOption }}</span>
          </label>
          <label class="sp-p14__field--check">
            <input
              v-model="installSource"
              type="radio"
              value="package"
              :disabled="actionPending"
              data-install-source="package"
            />
            <span>{{ zhCN.p14.install.packageOption }}</span>
          </label>
        </div>
        <label v-if="installSource === 'package'" class="sp-p14__field">
          <span class="sp-p14__field-label">{{ zhCN.p14.install.packagePathLabel }}</span>
          <input
            v-model="installPackagePath"
            class="sp-p14__field-control sp-mono"
            type="text"
            :placeholder="zhCN.p14.install.packagePathPlaceholder"
            :disabled="actionPending"
            data-install-package-path
          />
          <span class="sp-p14__field-hint">{{ zhCN.p14.install.packagePathHint }}</span>
        </label>
        <p class="sp-p14__hint" data-p14="install-package-note">
          {{ zhCN.p14.install.packageHint }}
        </p>
      </div>
      <p v-if="dialogError" class="sp-p14__dialog-error" data-p14="dialog-error" role="alert">
        {{ dialogError }}
      </p>
    </ConfirmDialog>
  </div>
</template>

<style scoped>
.sp-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sp-p14__meta {
  margin-left: 5px;
  color: var(--sp-text);
}

.sp-p14__readonly {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px 12px;
  padding: 8px 12px;
  border: 1px solid var(--sp-info-border);
  border-left: 3px solid var(--sp-info);
  border-radius: var(--sp-radius);
  background: var(--sp-info-soft);
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--sp-text);
}

.sp-p14__readonly-label {
  flex: none;
  font-weight: 600;
  color: var(--sp-info);
}

.sp-p14__readonly-text {
  flex: 1 1 320px;
  min-width: 0;
}

.sp-p14__lock {
  display: inline-flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 5px;
  font-size: 10.5px;
}

.sp-p14__lock code {
  color: var(--sp-text);
}

.sp-p14__lock-hint {
  color: var(--sp-faint);
}

.sp-p14__action-error {
  padding: 8px 12px;
  border: 1px solid var(--sp-danger-border);
  border-left: 3px solid var(--sp-danger);
  border-radius: var(--sp-radius);
  background: var(--sp-danger-soft);
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--sp-danger);
  word-break: break-word;
}

.sp-p14__dialog-error {
  margin-top: 8px;
  font-size: 12px;
  color: var(--sp-danger);
  word-break: break-word;
}

.sp-p14__install-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
  padding: 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface-sunken);
}

.sp-p14__install-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
}

.sp-p14__kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.sp-p14__skills {
  overflow: hidden;
}

.sp-p14__skills :deep(.el-table__row) {
  cursor: pointer;
}

.sp-p14__publisher {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sp-p14__row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 2px;
}

.sp-p14__row-actions--start {
  justify-content: flex-start;
}

.sp-p14__caps {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.sp-p14__cap {
  gap: 5px;
  font-size: 10px;
}

.sp-p14__risk {
  font-weight: 600;
}

.sp-p14__risk--l0 {
  border-color: var(--sp-success-border);
  background: var(--sp-success-soft);
  color: var(--sp-success);
}

.sp-p14__risk--l1 {
  border-color: var(--sp-info-border);
  background: var(--sp-info-soft);
  color: var(--sp-info);
}

.sp-p14__risk--l2 {
  border-color: var(--sp-warning-border);
  background: var(--sp-warning-soft);
  color: var(--sp-warning);
}

.sp-p14__risk--l3 {
  border-color: var(--sp-danger-border);
  background: var(--sp-danger-soft);
  color: var(--sp-danger);
}

.sp-p14__runs {
  overflow: hidden;
}

.sp-p14__runs-tools {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
}

.sp-p14__filter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.sp-p14__filter-label {
  font-size: 10.5px;
  color: var(--sp-muted);
}

.sp-p14__control {
  height: 26px;
  padding: 0 8px;
  border: 1px solid var(--sp-border-strong);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  font-size: 11.5px;
  color: var(--sp-text);
}

.sp-p14__control:focus {
  border-color: var(--sp-primary);
  outline: none;
}

.sp-p14__detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sp-p14__detail-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--sp-border);
}

.sp-p14__detail-id {
  font-size: 14px;
  font-weight: 600;
  color: var(--sp-text);
}

.sp-p14__sub {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sp-p14__sub h3 {
  font-size: 12px;
  font-weight: 650;
  color: var(--sp-text);
}

.sp-p14__desc {
  font-size: 12px;
  line-height: 1.6;
  color: var(--sp-muted);
}

.sp-p14__kv {
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: 5px 12px;
  margin: 0;
  font-size: 11.5px;
}

.sp-p14__kv dt {
  color: var(--sp-faint);
}

.sp-p14__kv dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
  color: var(--sp-text);
}

.sp-p14__install-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sp-p14__hint {
  font-size: 10.5px;
  line-height: 1.55;
  color: var(--sp-faint);
}

.sp-p14__cap-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.sp-p14__cap-item {
  padding: 7px 9px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-bg);
}

.sp-p14__cap-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11.5px;
}

.sp-p14__cap-desc {
  margin-top: 3px;
  font-size: 11px;
  line-height: 1.55;
  color: var(--sp-muted);
}

.sp-p14__code-block {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.sp-p14__code-label {
  font-size: 10.5px;
  color: var(--sp-faint);
}

.sp-p14__pre {
  max-height: 190px;
  margin: 0;
  padding: 7px 9px;
  overflow: auto;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface-sunken);
  font-size: 10.5px;
  line-height: 1.55;
  color: var(--sp-text);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.sp-p14__keys {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
}

.sp-p14__empty-line {
  padding: 7px 0;
  font-size: 11.5px;
  color: var(--sp-faint);
}

.sp-p14__break {
  overflow-wrap: anywhere;
}

.sp-p14__binding-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface-sunken);
}

.sp-p14__binding-form-head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px 10px;
}

.sp-p14__binding-form-head h4 {
  font-size: 11.5px;
  font-weight: 650;
  color: var(--sp-text);
}

.sp-p14__binding-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 10px;
}

.sp-p14__field {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.sp-p14__field--check {
  flex-direction: row;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--sp-text);
}

.sp-p14__field-label {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--sp-muted);
}

.sp-p14__field-control {
  width: 100%;
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--sp-border);
  border-radius: var(--sp-radius);
  background: var(--sp-surface);
  font-size: 12px;
  color: var(--sp-text);
}

.sp-p14__field-control:focus {
  border-color: var(--sp-primary);
  outline: none;
  box-shadow: var(--sp-focus);
}

.sp-p14__field-hint {
  font-size: 10px;
  color: var(--sp-faint);
}

.sp-p14__binding-error {
  font-size: 11.5px;
  color: var(--sp-danger);
  word-break: break-word;
}

.sp-p14__binding-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 960px) {
  .sp-p14__kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .sp-p14__kv {
    grid-template-columns: 1fr;
    gap: 2px;
  }
  .sp-p14__kv dd {
    margin-bottom: 4px;
  }
  .sp-p14__binding-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
