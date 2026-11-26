import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'

import { ApiError } from '../src/api/client'
import type {
  SkillBinding,
  SkillCapability,
  SkillCatalogResponse,
  SkillDetailResponse,
  SkillInstallation,
  SkillManifestItem,
  SkillRun,
  SkillRunsResponse,
  SkillVerifyResponse,
} from '../src/api/types'
import {
  EMPTY_SKILL_RUNS_COPY,
  EMPTY_SKILLS_COPY,
  SKILL_READONLY_NOTE,
  zhCN,
} from '../src/i18n/zh-CN'
import P14Skills from '../src/pages/P14Skills.vue'

const api = vi.hoisted(() => ({
  fetchSkillCatalog: vi.fn(),
  fetchSkillRuns: vi.fn(),
  fetchSkillDetail: vi.fn(),
  fetchSkillBindings: vi.fn(),
  installSkill: vi.fn(),
  verifySkill: vi.fn(),
  enableSkill: vi.fn(),
  disableSkill: vi.fn(),
  putSkillBinding: vi.fn(),
  deleteSkillBinding: vi.fn(),
}))

vi.mock('../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/client')>()
  return { ...actual, ...api }
})

function makeCapability(
  name: string,
  risk: SkillCapability['risk'],
  riskLabel: string,
  description: string,
): SkillCapability {
  return { name, risk, risk_label: riskLabel, description }
}

function makeDistribution(overrides: Partial<SkillManifestItem> = {}): SkillManifestItem {
  return {
    id: '1688-distribution',
    version: '1.4.0',
    publisher: '1688aiinfra',
    trust: 'official',
    license: 'MIT',
    description: '1688 分销选品/商品/铺货 CLI；当前接入 sourcing.search，铺货能力留 S12。',
    adapter: 'modules.mod_1688_ops.skill_adapter:DistributionSourcingAdapter',
    capabilities: [
      makeCapability('sourcing.search', 'L0', '只读', '1688 关键词选品，返回候选货源 JSON'),
    ],
    entrypoints: {
      cli: {
        command: 'python3 scripts/cli.py',
        allowed_commands: ['product_search_helper.search'],
      },
    },
    limits: { timeout_seconds: 30, max_concurrency: 2, egress: ['clawhub.1688.com', '*.1688.com'] },
    credentials: [],
    config: { fixtures: 'modules/mod_1688_ops/fixtures/offers.json' },
    checksum: 'adapter-only',
    status: 'adapter-only',
    installed_at: null,
    bindings: [{ platform: '*', shop_id: '*', enabled: true, priority: 20 }],
    ...overrides,
  }
}

function makeUtp(overrides: Partial<SkillManifestItem> = {}): SkillManifestItem {
  return {
    id: '1688-utp-shopping',
    version: '2.4.2',
    publisher: '1688aiinfra',
    trust: 'verified',
    license: 'MIT-0',
    description: '1688 搜品/加购/checkout；HITL，支付必须人工完成。',
    adapter: 'modules.mod_1688_ops.skill_adapter:UtpPurchaseAdapter',
    capabilities: [
      makeCapability(
        'purchase.checkout',
        'L2',
        '外部写（需审批）',
        '创建 1688 checkout；不代提交、不代付',
      ),
    ],
    entrypoints: {
      cli: {
        command: 'utp invoke',
        allowed_commands: ['utp_catalog_search', 'utp_checkout_create', 'utp_checkout_get'],
      },
    },
    limits: { timeout_seconds: 30, max_concurrency: 1, egress: ['ucp-b2b.com'] },
    credentials: ['ali_1688_ak'],
    config: {},
    checksum: 'adapter-only',
    status: 'adapter-only',
    installed_at: null,
    bindings: [
      { platform: '*', shop_id: '*', enabled: true, priority: 10 },
      { platform: 'demo', shop_id: 'SHOP-0001', enabled: false, priority: 5 },
    ],
    ...overrides,
  }
}

function makeInstallation(
  status: SkillInstallation['status'],
  overrides: Partial<SkillInstallation> = {},
): SkillInstallation {
  return {
    skill_id: '1688-distribution',
    version: '1.4.0',
    status,
    checksum: 'sha256:abc',
    manifest_path: 'skills/1688-distribution/manifest.yaml',
    installed_by: 'owner',
    installed_at: '2026-11-26T12:00:00+08:00',
    ...overrides,
  }
}

const PACKAGE_CHECKSUM = 'sha256:package-abc123'

function makePackageInstallation(
  overrides: Partial<SkillInstallation> = {},
): SkillInstallation {
  return makeInstallation('INSTALLED', {
    details: {
      kind: 'package',
      package_checksum: PACKAGE_CHECKSUM,
      package_path: 'storage/skill_packages/distribution.zip',
      files: ['skill.yaml', 'scripts/cli.py'],
    },
    ...overrides,
  })
}

function makeRun(overrides: Partial<SkillRun> = {}): SkillRun {
  return {
    run_id: 'run-s10-20261126-001',
    skill_id: '1688-distribution',
    skill_version: '1.4.0',
    capability: 'sourcing.search',
    scene: 'S10',
    platform: 'demo',
    shop_id: 'SHOP-0001',
    status: 'SUCCEEDED',
    latency_ms: 128,
    error_code: null,
    created_at: '2026-11-26T10:00:00+08:00',
    ...overrides,
  }
}

function makeCatalog(
  items: SkillManifestItem[] = [makeDistribution(), makeUtp()],
  overrides: Partial<SkillCatalogResponse> = {},
): SkillCatalogResponse {
  return {
    items,
    count: items.length,
    lock_path: 'skills.lock',
    empty_copy: EMPTY_SKILLS_COPY,
    note: 'S2b：OWNER 可清单/安装包安装、校验、启停、按店绑定；UTP 真实包与凭据在后续',
    ...overrides,
  }
}

function makeRuns(
  items: SkillRun[] = [
    makeRun(),
    makeRun({
      run_id: 'run-s11-20261126-002',
      skill_id: '1688-utp-shopping',
      skill_version: '2.4.2',
      capability: 'purchase.checkout',
      scene: 'S11',
      status: 'FAILED',
      latency_ms: 30000,
      error_code: 'E_SKILL_TIMEOUT',
      created_at: '2026-11-26T11:00:00+08:00',
    }),
  ],
  overrides: Partial<SkillRunsResponse> = {},
): SkillRunsResponse {
  return { items, empty_copy: EMPTY_SKILL_RUNS_COPY, ...overrides }
}

function makeDetail(overrides: Partial<SkillDetailResponse> = {}): SkillDetailResponse {
  return {
    ...makeUtp(),
    installation: null,
    runs: [
      makeRun({
        run_id: 'run-s11-20261126-002',
        skill_id: '1688-utp-shopping',
        skill_version: '2.4.2',
        capability: 'purchase.checkout',
        scene: 'S11',
        status: 'FAILED',
        latency_ms: 30000,
        error_code: 'E_SKILL_TIMEOUT',
        created_at: '2026-11-26T11:00:00+08:00',
      }),
    ],
    ...overrides,
  }
}

let wrapper: VueWrapper | null = null

beforeEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
  localStorage.clear()
  localStorage.setItem('shoppivot.token', 'test-token')
  localStorage.setItem('shoppivot.role', 'OWNER')
  api.fetchSkillCatalog.mockResolvedValue(makeCatalog())
  api.fetchSkillRuns.mockResolvedValue(makeRuns())
  api.fetchSkillDetail.mockResolvedValue(makeDetail())
  api.fetchSkillBindings.mockResolvedValue({ items: [], note: '' })
  api.installSkill.mockResolvedValue(makeInstallation('INSTALLED'))
  api.verifySkill.mockResolvedValue({
    skill_id: '1688-distribution',
    ok: true,
    expected: 'sha256:abc',
    actual: 'sha256:abc',
  })
  api.enableSkill.mockResolvedValue(makeInstallation('ENABLED'))
  api.disableSkill.mockResolvedValue(makeInstallation('DISABLED'))
  api.putSkillBinding.mockResolvedValue({
    platform: '*',
    shop_id: '*',
    enabled: true,
    priority: 10,
    credential_ref: '',
  })
  api.deleteSkillBinding.mockResolvedValue({ ok: true })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  localStorage.clear()
})

async function mountPage(): Promise<VueWrapper> {
  wrapper = mount(P14Skills, {
    attachTo: document.body,
    global: { plugins: [createPinia()] },
  })
  await flushPromises()
  await flushPromises()
  return wrapper
}

function buttonTexts(): string[] {
  return Array.from(document.querySelectorAll('button')).map((button) =>
    (button.textContent ?? '').trim(),
  )
}

function findButtonByText(text: string): HTMLButtonElement | null {
  const buttons = Array.from(document.querySelectorAll('button')) as HTMLButtonElement[]
  return buttons.find((button) => (button.textContent ?? '').trim() === text) ?? null
}

function skillRow(page: VueWrapper, skillId: string) {
  const row = page
    .findAll('.el-table__row')
    .find((candidate) => candidate.text().includes(skillId))
  if (!row) throw new Error(`未找到 Skill 行: ${skillId}`)
  return row
}

function setInput(selector: string, value: string): void {
  const input = document.querySelector(selector) as HTMLInputElement | null
  if (!input) throw new Error(`未找到输入框: ${selector}`)
  input.value = value
  input.dispatchEvent(new Event('input'))
}

/** 切换安装弹窗里的安装方式（radio 通过 change 事件同步 v-model）。 */
function chooseInstallSource(source: 'manifest' | 'package'): void {
  const radio = document.querySelector(
    `[data-install-source="${source}"]`,
  ) as HTMLInputElement | null
  if (!radio) throw new Error(`未找到安装方式单选框: ${source}`)
  radio.checked = true
  radio.dispatchEvent(new Event('change'))
}

describe('P14 技能中心（S2b：OWNER 可清单/安装包安装）', () => {
  it('渲染 2 个 Skill、信任徽标、能力/风险中文标签与锁文件路径', async () => {
    const page = await mountPage()

    expect(api.fetchSkillCatalog).toHaveBeenCalledTimes(1)
    expect(api.fetchSkillRuns).toHaveBeenCalledWith({ limit: 50 })

    const kpis = page.findAll('.sp-kpi')
    expect(kpis.length).toBe(4)
    expect(kpis[0].text()).toContain(zhCN.p14.kpi.skills)
    expect(kpis[0].text()).toContain('2')
    expect(kpis[1].text()).toContain(zhCN.p14.kpi.trusted)
    expect(kpis[1].text()).toContain('2')
    expect(kpis[2].text()).toContain(zhCN.p14.kpi.capabilities)
    expect(kpis[2].text()).toContain('2')
    expect(kpis[3].text()).toContain(zhCN.p14.kpi.failedRuns)
    expect(kpis[3].text()).toContain('1')

    const notes = page.find('[data-p14="readonly-note"]')
    expect(notes.text()).toContain(SKILL_READONLY_NOTE)
    expect(notes.text()).toContain('S2b')
    expect(page.find('[data-p14="lock-path"]').text()).toBe('skills.lock')

    const skills = page.find('[data-p14="skills"]')
    expect(skills.findAll('.el-table__row').length).toBe(2)
    expect(skills.text()).toContain('1688-distribution')
    expect(skills.text()).toContain('1688-utp-shopping')
    expect(skills.text()).toContain('1.4.0')
    expect(skills.text()).toContain('2.4.2')
    expect(skills.text()).toContain('1688aiinfra')
    expect(skills.text()).toContain('MIT')
    expect(skills.text()).toContain(zhCN.p14.trustLabels.official)
    expect(skills.text()).toContain(zhCN.p14.trustLabels.verified)
    expect(skills.text()).toContain('sourcing.search')
    expect(skills.text()).toContain('purchase.checkout')
    expect(skills.text()).toContain(zhCN.p14.riskLabels.L0)
    expect(skills.text()).toContain(zhCN.p14.riskLabels.L2)
    expect(page.find('[data-trust="official"]').exists()).toBe(true)
    expect(page.find('[data-trust="verified"]').exists()).toBe(true)
    expect(page.find('[data-trust="untrusted"]').exists()).toBe(false)
  })

  it('点击行抽屉展示 adapter、bindings 与最近运行记录', async () => {
    const page = await mountPage()

    await page.find('[data-skill-id="1688-utp-shopping"]').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(api.fetchSkillDetail).toHaveBeenCalledWith('1688-utp-shopping')
    const drawer = document.querySelector('[data-p14="drawer"]')
    expect(drawer).not.toBeNull()
    const text = drawer?.textContent ?? ''
    expect(text).toContain('1688-utp-shopping')
    expect(text).toContain('modules.mod_1688_ops.skill_adapter:UtpPurchaseAdapter')
    expect(text).toContain(zhCN.p14.drawer.credentials)
    expect(text).toContain('ali_1688_ak')
    expect(text).toContain(zhCN.p14.drawer.bindingEnabled)
    expect(text).toContain(zhCN.p14.drawer.bindingDisabled)

    const bindings = document.querySelector('[data-p14="drawer-bindings"]')
    expect(bindings?.textContent ?? '').toContain('SHOP-0001')
    expect(bindings?.textContent ?? '').toContain('10')

    const runs = document.querySelector('[data-p14="drawer-runs"]')
    expect(runs?.textContent ?? '').toContain('1688-utp-shopping')
    expect(runs?.textContent ?? '').toContain('purchase.checkout')
    expect(runs?.textContent ?? '').toContain('S11')
    expect(runs?.textContent ?? '').toContain('30000 ms')
    expect(runs?.textContent ?? '').toContain(zhCN.p14.runStatusLabels.FAILED)
    expect(runs?.textContent ?? '').toContain('E_SKILL_TIMEOUT')
  })

  it('运行记录空态使用接口 empty_copy 原文', async () => {
    const apiEmptyCopy = '暂无 Skill 运行记录（接口原文）'
    api.fetchSkillRuns.mockResolvedValue(makeRuns([], { empty_copy: apiEmptyCopy }))

    const page = await mountPage()

    const runs = page.find('[data-p14="runs"]')
    expect(runs.text()).toContain(apiEmptyCopy)
    expect(runs.text()).toContain(zhCN.p14.runsEmptyHint)
    expect(runs.find('.el-table__row').exists()).toBe(false)
    expect(page.findAll('.sp-kpi')[3].text()).toContain('0')
  })

  it('403 时展示无权限提示，不渲染技能清单', async () => {
    api.fetchSkillCatalog.mockRejectedValue(
      new ApiError({
        code: 'E403',
        layer: 'SYS',
        userMessage: zhCN.p14.forbidden,
        status: 403,
      }),
    )

    const page = await mountPage()

    expect(page.text()).toContain(zhCN.p14.forbidden)
    expect(page.text()).toContain(zhCN.p14.forbiddenHint)
    expect(page.find('.sp-state--forbidden').exists()).toBe(true)
    expect(page.find('[data-p14="skills"]').exists()).toBe(false)
    expect(page.find('[data-p14="kpis"]').exists()).toBe(false)
  })

  it('VIEWER 只读：不渲染安装/校验/启用/停用/绑定与执行入口', async () => {
    localStorage.setItem('shoppivot.role', 'VIEWER')
    const page = await mountPage()

    const forbiddenWords = ['安装', '校验', '启用', '停用', '执行', '卸载', '升级', '一键']
    for (const text of buttonTexts()) {
      for (const word of forbiddenWords) {
        expect(text).not.toContain(word)
      }
    }

    expect(page.text()).not.toContain('一键执行')
    expect(page.text()).not.toContain('一键优化')
    expect(page.find('[data-skill-action]').exists()).toBe(false)
    expect(page.find('[data-p14="readonly-role-hint"]').exists()).toBe(true)
    expect(document.querySelector('[data-action*="install"]')).toBeNull()
    expect(document.querySelector('[data-action*="execute"]')).toBeNull()
    expect(document.querySelector('[data-action*="enable"]')).toBeNull()

    await page.find('[data-skill-id="1688-distribution"]').trigger('click')
    await flushPromises()
    await flushPromises()

    for (const text of buttonTexts()) {
      for (const word of forbiddenWords) {
        expect(text).not.toContain(word)
      }
    }
    expect(document.querySelector('[data-drawer-action]')).toBeNull()
    expect(document.querySelector('[data-p14="binding-form"]')).toBeNull()
    expect(document.querySelector('[data-binding-delete]')).toBeNull()
  })

  it('adapter-only 显示「安装」，确认后调用 install 并刷新为 INSTALLED', async () => {
    let items: SkillManifestItem[] = [makeDistribution()]
    api.fetchSkillCatalog.mockImplementation(async () => makeCatalog(items))
    api.installSkill.mockImplementation(async (skillId: string) => {
      items = [
        {
          ...makeDistribution(),
          status: 'INSTALLED',
          checksum: 'sha256:abc',
          installed_at: '2026-11-26T12:00:00+08:00',
        },
      ]
      return makeInstallation('INSTALLED', { skill_id: skillId, note: 'S2a 清单级安装' })
    })

    const page = await mountPage()
    const row = skillRow(page, '1688-distribution')
    expect(row.text()).toContain(zhCN.p14.statusLabels['adapter-only'])

    const installButton = row.find('[data-skill-action="install"]')
    expect(installButton.exists()).toBe(true)
    expect(installButton.text()).toContain(zhCN.p14.actions.install)

    await installButton.trigger('click')
    await flushPromises()

    // 行内动作按钮不应触发行点击（不打开抽屉）
    expect(api.fetchSkillDetail).not.toHaveBeenCalled()

    const confirmButton = findButtonByText(zhCN.p14.actions.installConfirm)
    expect(confirmButton).not.toBeNull()
    confirmButton?.click()
    await flushPromises()
    await flushPromises()

    expect(api.installSkill).toHaveBeenCalledWith('1688-distribution')
    expect(api.fetchSkillCatalog.mock.calls.length).toBeGreaterThan(1)

    const refreshed = skillRow(page, '1688-distribution')
    expect(refreshed.text()).toContain(zhCN.p14.statusLabels.INSTALLED)
    expect(refreshed.find('[data-skill-action="enable"]').exists()).toBe(true)
    expect(refreshed.find('[data-skill-action="verify"]').exists()).toBe(true)
    expect(refreshed.find('[data-skill-action="install"]').exists()).toBe(false)
  })

  it('INSTALLED 显示「启用」，enable 后为 ENABLED 并显示「停用」', async () => {
    let items: SkillManifestItem[] = [
      { ...makeDistribution(), status: 'INSTALLED', checksum: 'sha256:abc' },
    ]
    api.fetchSkillCatalog.mockImplementation(async () => makeCatalog(items))
    api.enableSkill.mockImplementation(async (skillId: string) => {
      items = [{ ...items[0], status: 'ENABLED' }]
      return makeInstallation('ENABLED', { skill_id: skillId })
    })

    const page = await mountPage()
    let row = skillRow(page, '1688-distribution')
    expect(row.text()).toContain(zhCN.p14.statusLabels.INSTALLED)
    expect(row.find('[data-skill-action="verify"]').exists()).toBe(true)

    await row.find('[data-skill-action="enable"]').trigger('click')
    await flushPromises()
    const confirmButton = findButtonByText(zhCN.p14.actions.enableConfirm)
    expect(confirmButton).not.toBeNull()
    confirmButton?.click()
    await flushPromises()
    await flushPromises()

    expect(api.enableSkill).toHaveBeenCalledWith('1688-distribution')

    row = skillRow(page, '1688-distribution')
    expect(row.text()).toContain(zhCN.p14.statusLabels.ENABLED)
    expect(row.find('[data-skill-action="disable"]').exists()).toBe(true)
    expect(row.find('[data-skill-action="enable"]').exists()).toBe(false)

    // ENABLED → 停用需二次确认，调用 disable 后回到 DISABLED
    items = [{ ...items[0], status: 'DISABLED' }]
    await row.find('[data-skill-action="disable"]').trigger('click')
    await flushPromises()
    const disableConfirm = findButtonByText(zhCN.p14.actions.disableConfirm)
    expect(disableConfirm).not.toBeNull()
    disableConfirm?.click()
    await flushPromises()
    await flushPromises()

    expect(api.disableSkill).toHaveBeenCalledWith('1688-distribution')
    row = skillRow(page, '1688-distribution')
    expect(row.text()).toContain(zhCN.p14.statusLabels.DISABLED)
    expect(row.find('[data-skill-action="enable"]').exists()).toBe(true)
    expect(row.find('[data-skill-action="disable"]').exists()).toBe(false)
  })

  it('校验按钮调用 verify 并展示 ok / expected / actual，未通过为红色', async () => {
    const items: SkillManifestItem[] = [
      { ...makeDistribution(), status: 'ENABLED', checksum: 'sha256:abc' },
    ]
    api.fetchSkillCatalog.mockImplementation(async () => makeCatalog(items))
    api.verifySkill.mockResolvedValueOnce({
      skill_id: '1688-distribution',
      ok: true,
      expected: 'sha256:abc',
      actual: 'sha256:abc',
    })
    api.verifySkill.mockResolvedValueOnce({
      skill_id: '1688-distribution',
      ok: false,
      expected: 'sha256:abc',
      actual: 'sha256:def',
    } satisfies SkillVerifyResponse)

    const page = await mountPage()
    await skillRow(page, '1688-distribution')
      .find('[data-skill-action="verify"]')
      .trigger('click')
    await flushPromises()
    await flushPromises()

    expect(api.verifySkill).toHaveBeenCalledWith('1688-distribution')
    const result = page.find('[data-p14="verify-result"]')
    expect(result.exists()).toBe(true)
    expect(result.text()).toContain(zhCN.p14.verify.okLabel)
    expect(result.text()).toContain(zhCN.p14.verify.okValue(true))
    expect(result.text()).toContain(zhCN.p14.verify.expected)
    expect(result.text()).toContain(zhCN.p14.verify.actual)
    expect(result.text()).toContain('sha256:abc')
    expect(result.find('[data-verify-ok="true"]').exists()).toBe(true)
    expect(result.find('.sp-verify--danger').exists()).toBe(false)

    await skillRow(page, '1688-distribution')
      .find('[data-skill-action="verify"]')
      .trigger('click')
    await flushPromises()
    await flushPromises()

    const failed = page.find('[data-p14="verify-result"]')
    expect(failed.text()).toContain(zhCN.p14.verify.failedLabel)
    expect(failed.text()).toContain(zhCN.p14.verify.okValue(false))
    expect(failed.text()).toContain('sha256:def')
    expect(failed.find('[data-verify-ok="false"]').exists()).toBe(true)
    expect(failed.find('.sp-verify--danger').exists()).toBe(true)
  })

  it('绑定表单保存调用 PUT、列表展示 credential_ref，删除调用 DELETE', async () => {
    let bindingStore: SkillBinding[] = [
      { platform: '*', shop_id: '*', enabled: true, priority: 10 },
    ]
    api.fetchSkillCatalog.mockImplementation(async () =>
      makeCatalog([makeUtp({ status: 'ENABLED', bindings: bindingStore })]),
    )
    api.fetchSkillDetail.mockImplementation(async () =>
      makeDetail({ status: 'ENABLED', bindings: bindingStore }),
    )
    api.fetchSkillBindings.mockImplementation(async () => ({
      items: bindingStore,
      note: '凭据只存引用；解析器按 platform + shop_id 匹配',
    }))
    api.putSkillBinding.mockImplementation(async (_skillId: string, payload: SkillBinding) => {
      const saved: SkillBinding = {
        platform: payload.platform,
        shop_id: payload.shop_id,
        enabled: payload.enabled,
        priority: payload.priority,
        credential_ref: payload.credential_ref,
      }
      bindingStore = [
        ...bindingStore.filter(
          (item) => !(item.platform === saved.platform && item.shop_id === saved.shop_id),
        ),
        saved,
      ]
      return saved
    })
    api.deleteSkillBinding.mockImplementation(
      async (_skillId: string, platform: string, shopId: string) => {
        bindingStore = bindingStore.filter(
          (item) => !(item.platform === platform && item.shop_id === shopId),
        )
        return { ok: true }
      },
    )

    const page = await mountPage()
    await page.find('[data-skill-id="1688-utp-shopping"]').trigger('click')
    await flushPromises()
    await flushPromises()

    // 表单默认值：platform/shop 均为 *，priority 10，enabled
    expect((document.querySelector('[data-binding-field="platform"]') as HTMLInputElement).value)
      .toBe('*')
    expect((document.querySelector('[data-binding-field="shop_id"]') as HTMLInputElement).value)
      .toBe('*')
    expect((document.querySelector('[data-binding-field="priority"]') as HTMLInputElement).value)
      .toBe('10')
    expect(
      (document.querySelector('[data-binding-field="credential_ref"]') as HTMLInputElement)
        .placeholder,
    ).toBe('vault://...')
    expect((document.querySelector('[data-binding-field="enabled"]') as HTMLInputElement).checked)
      .toBe(true)

    setInput('[data-binding-field="shop_id"]', 'SHOP-0001')
    setInput('[data-binding-field="priority"]', '30')
    setInput('[data-binding-field="credential_ref"]', 'vault://1688/utp')
    await flushPromises()

    const saveButton = document.querySelector('[data-binding-save]') as HTMLButtonElement | null
    expect(saveButton).not.toBeNull()
    saveButton?.click()
    await flushPromises()
    await flushPromises()

    expect(api.putSkillBinding).toHaveBeenCalledWith('1688-utp-shopping', {
      platform: '*',
      shop_id: 'SHOP-0001',
      enabled: true,
      priority: 30,
      credential_ref: 'vault://1688/utp',
      config: {},
    })
    expect(api.fetchSkillBindings).toHaveBeenCalledWith('1688-utp-shopping')

    const bindingsTable = document.querySelector('[data-p14="drawer-bindings"]')
    expect(bindingsTable?.textContent ?? '').toContain('vault://1688/utp')
    expect(bindingsTable?.textContent ?? '').toContain('SHOP-0001')
    expect(bindingsTable?.textContent ?? '').toContain('30')

    const deleteButton = document.querySelector(
      '[data-binding-delete="*/SHOP-0001"]',
    ) as HTMLButtonElement | null
    expect(deleteButton).not.toBeNull()
    deleteButton?.click()
    await flushPromises()
    await flushPromises()

    expect(api.deleteSkillBinding).toHaveBeenCalledWith('1688-utp-shopping', '*', 'SHOP-0001')
    const cleared = document.querySelector('[data-p14="drawer-bindings"]')
    expect(cleared?.textContent ?? '').not.toContain('vault://1688/utp')
    expect(cleared?.textContent ?? '').not.toContain('SHOP-0001')
  })

  it('失败响应原样展示后端 message（409）', async () => {
    const backendMessage = 'Skill 校验和不匹配: 1688-distribution'
    api.fetchSkillCatalog.mockResolvedValue(makeCatalog([makeDistribution()]))
    api.installSkill.mockRejectedValue(
      new ApiError({
        code: 'E006',
        layer: 'CODE',
        message: backendMessage,
        userMessage: zhCN.errors.unknown,
        status: 409,
      }),
    )

    const page = await mountPage()
    await skillRow(page, '1688-distribution')
      .find('[data-skill-action="install"]')
      .trigger('click')
    await flushPromises()
    const confirmButton = findButtonByText(zhCN.p14.actions.installConfirm)
    expect(confirmButton).not.toBeNull()
    confirmButton?.click()
    await flushPromises()
    await flushPromises()

    expect(api.installSkill).toHaveBeenCalledWith('1688-distribution')
    const actionError = page.find('[data-p14="action-error"]')
    expect(actionError.exists()).toBe(true)
    expect(actionError.text()).toContain(backendMessage)
    expect(document.body.textContent ?? '').toContain(backendMessage)
    expect(skillRow(page, '1688-distribution').text()).toContain(
      zhCN.p14.statusLabels['adapter-only'],
    )
  })

  it('安装包：未填路径不发请求并提示；填写后按 package 调用 install 并刷新', async () => {
    let items: SkillManifestItem[] = [makeDistribution()]
    api.fetchSkillCatalog.mockImplementation(async () => makeCatalog(items))
    api.installSkill.mockImplementation(async (skillId: string) => {
      items = [
        {
          ...makeDistribution(),
          status: 'INSTALLED',
          checksum: 'sha256:abc',
          installed_at: '2026-11-26T12:00:00+08:00',
        },
      ]
      return makePackageInstallation({ skill_id: skillId })
    })

    const page = await mountPage()
    await skillRow(page, '1688-distribution')
      .find('[data-skill-action="install"]')
      .trigger('click')
    await flushPromises()

    // 默认清单安装：无路径输入，说明安装包不执行包内脚本
    expect(
      (document.querySelector('[data-install-source="manifest"]') as HTMLInputElement).checked,
    ).toBe(true)
    expect(document.querySelector('[data-install-package-path]')).toBeNull()
    expect(document.body.textContent ?? '').toContain(zhCN.p14.install.packageHint)

    chooseInstallSource('package')
    await flushPromises()

    const pathInput = document.querySelector(
      '[data-install-package-path]',
    ) as HTMLInputElement | null
    expect(pathInput).not.toBeNull()
    expect(pathInput?.placeholder).toBe('storage/skill_packages/xxx.zip')

    // 未填路径：不发请求，弹窗内提示必填
    findButtonByText(zhCN.p14.actions.installConfirm)?.click()
    await flushPromises()
    expect(api.installSkill).not.toHaveBeenCalled()
    expect(document.body.textContent ?? '').toContain(zhCN.p14.install.packageRequired)
    expect(document.querySelector('[data-p14="dialog-error"]')).not.toBeNull()

    // 填写路径后：按 source=package + package_path 调用并刷新
    setInput('[data-install-package-path]', 'distribution.zip')
    await flushPromises()
    findButtonByText(zhCN.p14.actions.installConfirm)?.click()
    await flushPromises()
    await flushPromises()

    expect(api.installSkill).toHaveBeenCalledWith('1688-distribution', {
      source: 'package',
      package_path: 'distribution.zip',
    })
    expect(api.fetchSkillCatalog.mock.calls.length).toBeGreaterThan(1)
    expect(skillRow(page, '1688-distribution').text()).toContain(
      zhCN.p14.statusLabels.INSTALLED,
    )
  })

  it('安装包响应 details.kind / package_checksum 在抽屉安装记录可见', async () => {
    let installed = false
    const installation = makePackageInstallation()
    api.fetchSkillCatalog.mockImplementation(async () =>
      makeCatalog([
        installed
          ? { ...makeDistribution(), status: 'INSTALLED', checksum: 'sha256:abc' }
          : makeDistribution(),
      ]),
    )
    api.fetchSkillDetail.mockImplementation(async () =>
      makeDetail({
        ...makeDistribution(),
        status: installed ? 'INSTALLED' : 'adapter-only',
        installation: installed ? installation : null,
        bindings: [],
        runs: [],
      }),
    )
    api.installSkill.mockImplementation(async (skillId: string) => {
      installed = true
      return { ...installation, skill_id: skillId }
    })

    const page = await mountPage()
    await page.find('[data-skill-id="1688-distribution"]').trigger('click')
    await flushPromises()
    await flushPromises()

    const drawerInstall = document.querySelector(
      '[data-drawer-action="install"]',
    ) as HTMLButtonElement | null
    expect(drawerInstall).not.toBeNull()
    drawerInstall?.click()
    await flushPromises()

    chooseInstallSource('package')
    await flushPromises()
    setInput('[data-install-package-path]', 'distribution.zip')
    await flushPromises()
    findButtonByText(zhCN.p14.actions.installConfirm)?.click()
    await flushPromises()
    await flushPromises()
    await flushPromises()

    expect(api.installSkill).toHaveBeenCalledWith('1688-distribution', {
      source: 'package',
      package_path: 'distribution.zip',
    })

    const detail = document.querySelector('[data-p14="installation-detail"]')
    expect(detail).not.toBeNull()
    const text = detail?.textContent ?? ''
    expect(text).toContain(zhCN.p14.installation.columns.kind)
    expect(text).toContain('安装包')
    expect(text).toContain('package')
    expect(text).toContain(zhCN.p14.installation.columns.packageChecksum)
    expect(text).toContain(PACKAGE_CHECKSUM)
  })

  it('安装包失败原样展示后端 message（409），不刷新目录', async () => {
    const backendMessage = 'Skill 包必须放在受控目录 skill_packages 下'
    api.fetchSkillCatalog.mockResolvedValue(makeCatalog([makeDistribution()]))
    api.installSkill.mockRejectedValue(
      new ApiError({
        code: 'E006',
        layer: 'CODE',
        message: backendMessage,
        userMessage: zhCN.errors.unknown,
        status: 409,
      }),
    )

    const page = await mountPage()
    await skillRow(page, '1688-distribution')
      .find('[data-skill-action="install"]')
      .trigger('click')
    await flushPromises()

    chooseInstallSource('package')
    await flushPromises()
    setInput('[data-install-package-path]', '../evil.zip')
    await flushPromises()

    const catalogCalls = api.fetchSkillCatalog.mock.calls.length
    findButtonByText(zhCN.p14.actions.installConfirm)?.click()
    await flushPromises()
    await flushPromises()

    expect(api.installSkill).toHaveBeenCalledWith('1688-distribution', {
      source: 'package',
      package_path: '../evil.zip',
    })
    expect(page.find('[data-p14="action-error"]').text()).toContain(backendMessage)
    expect(document.querySelector('[data-p14="dialog-error"]')?.textContent ?? '').toContain(
      backendMessage,
    )
    expect(api.fetchSkillCatalog.mock.calls.length).toBe(catalogCalls)
  })
})
