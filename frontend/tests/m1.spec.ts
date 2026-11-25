import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'

import { ApiError } from '../src/api/client'
import type {
  ExceptionRecord,
  MetricCardListItem,
  ReviewSummaryResponse,
  ReviewTicket,
  ReviewTicketsResponse,
  Subscription,
} from '../src/api/types'
import {
  CREDENTIALS_COPY,
  EMPTY_INVENTORY_COPY,
  EMPTY_SUBSCRIPTIONS_COPY,
  MASKED_COPY,
  RELEASE_FAILED_COPY,
  zhCN,
} from '../src/i18n/zh-CN'
import P02Reviews from '../src/pages/P02Reviews.vue'
import P03Inventory from '../src/pages/P03Inventory.vue'
import P10MetricCards from '../src/pages/P10MetricCards.vue'
import P11Workers from '../src/pages/P11Workers.vue'
import P12Access from '../src/pages/P12Access.vue'

const api = vi.hoisted(() => ({
  fetchReviewTickets: vi.fn(),
  fetchReviewSummary: vi.fn(),
  assignReviewTicket: vi.fn(),
  closeReviewTicket: vi.fn(),
  fetchInventoryReconciliation: vi.fn(),
  acceptInventorySuggestion: vi.fn(),
  ignoreInventorySuggestion: vi.fn(),
  fetchMetricCards: vi.fn(),
  fetchMetricCard: vi.fn(),
  fetchMetricDiff: vi.fn(),
  releaseMetricCard: vi.fn(),
  fetchWorkers: vi.fn(),
  fetchExceptions: vi.fn(),
  registerDemoWorker: vi.fn(),
  fetchIdentityRoles: vi.fn(),
  fetchSubscriptions: vi.fn(),
  createSubscription: vi.fn(),
  deleteSubscription: vi.fn(),
  fetchNotificationTemplates: vi.fn(),
}))

vi.mock('../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/client')>()
  return { ...actual, ...api }
})

let wrapper: VueWrapper | null = null

function setRole(role: string): void {
  localStorage.clear()
  localStorage.setItem('shoppivot.token', 'test-token')
  localStorage.setItem('shoppivot.role', role)
}

function mountPage(component: unknown): VueWrapper {
  wrapper = mount(component as never, {
    attachTo: document.body,
    global: { plugins: [createPinia()] },
  })
  return wrapper
}

const ticket: ReviewTicket = {
  ticket_id: 'tkt-1',
  run_id: 'run-s05',
  platform: 'demo',
  shop_id: 'SHOP-0001',
  review_id: 'rv-1001',
  sku: 'SKU-1',
  rating: 2,
  dsr: 3.2,
  content_masked: '买家反馈商品破损',
  hit_rule: 'rating<=3',
  severity: 'HIGH',
  status: 'OPEN',
  assignee: null,
  sla_due_at: '2026-11-26T10:00:00+08:00',
  created_at: '2026-11-25T10:00:00+08:00',
  closed_at: null,
  resolution: null,
  evidence_ref: 'ods-1',
  remaining_seconds: 3600,
  overdue: false,
}

const summary: ReviewSummaryResponse = {
  platform: 'demo',
  shop_id: 'SHOP-0001',
  counts: { OPEN: 1, ASSIGNED: 0, CLOSED: 0 },
  open: 1,
  assigned: 0,
  closed: 0,
  overdue: 0,
  trend: [
    { stat_date: '2026-11-24', dsr: 4.256, count: 12 },
    { stat_date: '2026-11-25', dsr: 3.5, count: 8 },
  ],
  empty_copy: '暂无差评或问答待处理',
}

const ticketsPayload: ReviewTicketsResponse = {
  items: [ticket],
  counts: { OPEN: 1 },
  empty_copy: '暂无差评或问答待处理',
  readonly: false,
}

const metricRow: MetricCardListItem = {
  metric_code: 'cvr',
  display_name: '转化率',
  version: '1.0',
  unit: '%',
  additivity: 'RATIO',
  null_policy: 'NO_DATA',
  source_mapping: 'dws_daily.cvr',
  release: null,
}

const exception: ExceptionRecord = {
  id: 1,
  run_id: 'run-s01',
  node_id: 'T3',
  err_code: 'E003',
  err_layer: 'UI',
  message: '选择器失效',
  retryable: true,
  status: 'OPEN',
  screenshot_ref: null,
  details: {},
  created_at: '2026-11-25T10:00:00+08:00',
}

const subscription: Subscription = {
  id: 1,
  name: '日报订阅',
  event: 'EVT-01',
  receiver: 'owner',
  channel: 'CONSOLE',
  window: '昨日',
  thresholds: { cvr_min: 3.5 },
  silent_window: null,
  enabled: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  document.body.innerHTML = ''
  api.assignReviewTicket.mockResolvedValue({ ticket_id: 'tkt-1', status: 'ASSIGNED', assignee: 'editor' })
  api.closeReviewTicket.mockResolvedValue({ ticket_id: 'tkt-1', status: 'CLOSED' })
  api.acceptInventorySuggestion.mockResolvedValue({
    suggestion_id: 'sug-1',
    status: 'ACCEPTED',
    note: '',
  })
  api.ignoreInventorySuggestion.mockResolvedValue({
    suggestion_id: 'sug-1',
    status: 'IGNORED',
    note: '',
  })
  api.registerDemoWorker.mockResolvedValue({
    worker_id: 'worker-headless-1',
    capabilities: ['EXPORT_PARSE'],
  })
  api.createSubscription.mockResolvedValue({ id: 2, status: 'CREATED' })
  api.deleteSubscription.mockResolvedValue({ id: 1, status: 'DELETED' })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  localStorage.clear()
})

describe('P03 库存与补货', () => {
  it('空态使用接口 empty_copy 原文，且不含自动补货/自动改库存文案', async () => {
    setRole('OWNER')
    api.fetchInventoryReconciliation.mockResolvedValue({
      run_id: null,
      window: null,
      diffs: [],
      suggestions: [],
      counts: {},
      snapshot_note: EMPTY_INVENTORY_COPY,
      empty_copy: EMPTY_INVENTORY_COPY,
      readonly: false,
    })

    const page = mountPage(P03Inventory)
    await flushPromises()
    await flushPromises()

    expect(page.text()).toContain(EMPTY_INVENTORY_COPY)
    expect(page.text()).not.toContain('自动补货')
    expect(page.text()).not.toContain('自动改库存')
    expect(page.text()).toContain(zhCN.p03.suggestionOnly)
  })

  it('KPI 与三方差异表按 counts 与 diff_type 渲染', async () => {
    setRole('OWNER')
    api.fetchInventoryReconciliation.mockResolvedValue({
      run_id: 'run-s07',
      window: { start: '2026-11-25', end: '2026-11-25' },
      diffs: [
        {
          run_id: 'run-s07',
          sku: 'SKU-1',
          platform_available: 3,
          erp_available: 20,
          wms_available: 18,
          platform_snapshot_at: '2026-11-25T09:00:00+08:00',
          erp_snapshot_at: null,
          wms_snapshot_at: '2026-11-25T09:05:00+08:00',
          diff_type: 'STOCKOUT',
          delta: -17,
          tolerance: 5,
        },
      ],
      suggestions: [
        {
          suggestion_id: 'sug-1',
          run_id: 'run-s07',
          sku: 'SKU-1',
          action: 'REPLENISH',
          quantity: 30,
          reason: '平台可售低于安全库存',
          status: 'OPEN',
          created_at: '2026-11-25T09:10:00+08:00',
        },
      ],
      counts: { STOCKOUT: 1 },
      snapshot_note: '平台/ERP/WMS 快照时间分别标注，时间窗不一致时不强行合并',
      empty_copy: EMPTY_INVENTORY_COPY,
      readonly: false,
    })

    const page = mountPage(P03Inventory)
    await flushPromises()
    await flushPromises()

    expect(page.text()).toContain('断货')
    expect(page.text()).toContain('补货')
    expect(page.text()).toContain('平台/ERP/WMS 快照时间分别标注')
    const buttonTexts = page.findAll('button').map((button) => button.text().trim())
    expect(buttonTexts).toContain(zhCN.p03.accept)
    expect(buttonTexts).toContain(zhCN.p03.ignore)
  })
})

describe('P02 评价与口碑', () => {
  it('只读角色隐藏派单/关闭按钮并提示只读', async () => {
    setRole('VIEWER')
    api.fetchReviewTickets.mockResolvedValue(ticketsPayload)
    api.fetchReviewSummary.mockResolvedValue(summary)

    const page = mountPage(P02Reviews)
    await flushPromises()
    await flushPromises()

    const buttonTexts = page.findAll('button').map((button) => button.text().trim())
    expect(buttonTexts).not.toContain(zhCN.p02.actions.assign)
    expect(buttonTexts).not.toContain(zhCN.p02.actions.close)
    expect(page.text()).toContain(MASKED_COPY)
    expect(page.text()).toContain(zhCN.p02.readonlyHint)
    expect(page.text()).toContain('4.26')
  })

  it('负责人可见派单/关闭按钮', async () => {
    setRole('OWNER')
    api.fetchReviewTickets.mockResolvedValue(ticketsPayload)
    api.fetchReviewSummary.mockResolvedValue(summary)

    const page = mountPage(P02Reviews)
    await flushPromises()
    await flushPromises()

    const buttonTexts = page.findAll('button').map((button) => button.text().trim())
    expect(buttonTexts).toContain(zhCN.p02.actions.assign)
    expect(buttonTexts).toContain(zhCN.p02.actions.close)
  })
})

describe('P10 口径与数据合同', () => {
  it('发布自检 409 时逐项渲染 details.release.checks 并显示失败文案', async () => {
    setRole('OWNER')
    api.fetchMetricCards.mockResolvedValue({
      items: [metricRow],
      empty_copy: '尚无已发布口径卡',
    })
    api.fetchMetricCard.mockResolvedValue({})
    api.fetchMetricDiff.mockResolvedValue({
      metric_code: 'cvr',
      from: null,
      to: '1.0',
      diffs: [],
      note: '没有可比较的历史版本；当前为该指标首个版本',
    })
    api.releaseMetricCard.mockRejectedValue(
      new ApiError({
        code: 'E007',
        layer: 'DATA',
        userMessage: RELEASE_FAILED_COPY,
        retryable: false,
        status: 409,
        details: {
          release: {
            metric_code: 'cvr',
            version: '1.0',
            gate_passed: false,
            checks: [
              { name: 'formula', passed: true, detail: '变量可求值' },
              { name: 'mapping', passed: true, detail: 'dws_daily.cvr' },
              { name: 'policy', passed: true, detail: 'RATIO/NO_DATA' },
              { name: 'probe', passed: false, detail: '探针包含多语句或写操作' },
              { name: 'evidence', passed: false, detail: '缺少 run_id / 报表证据' },
            ],
            checked_by: 'owner',
            checked_at: '2026-11-25T10:00:00+08:00',
          },
        },
      }),
    )

    const page = mountPage(P10MetricCards)
    await flushPromises()
    await flushPromises()

    const runButton = page
      .findAll('button')
      .find((button) => button.text().includes(zhCN.p10.runCheck))
    expect(runButton).toBeTruthy()
    await runButton?.trigger('click')
    await flushPromises()
    await flushPromises()
    await flushPromises()

    const bodyText = document.body.textContent ?? ''
    expect(bodyText).toContain(RELEASE_FAILED_COPY)
    expect(bodyText).toContain('探针包含多语句或写操作')
    expect(bodyText).toContain('缺少 run_id / 报表证据')
    expect(document.querySelectorAll('.sp-p10__check')).toHaveLength(5)
  })

  it('非负责人看不到运行发布自检按钮', async () => {
    setRole('EDITOR')
    api.fetchMetricCards.mockResolvedValue({
      items: [metricRow],
      empty_copy: '尚无已发布口径卡',
    })

    const page = mountPage(P10MetricCards)
    await flushPromises()
    await flushPromises()

    const buttonTexts = page.findAll('button').map((button) => button.text().trim())
    expect(buttonTexts).not.toContain(zhCN.p10.runCheck)
    expect(page.text()).toContain(zhCN.p10.readonlyHint)
  })
})

describe('P11 机器人与日志', () => {
  it('异常四层 UI/SYS/DATA/CODE 标签均存在并分组计数', async () => {
    setRole('OWNER')
    api.fetchWorkers.mockResolvedValue({
      items: [],
      online: 0,
      empty_copy: '暂无在线机器人',
    })
    api.fetchExceptions.mockResolvedValue({
      items: [
        { ...exception, id: 1, err_layer: 'UI', message: '界面异常' },
        { ...exception, id: 2, err_layer: 'SYS', message: '系统异常' },
        { ...exception, id: 3, err_layer: 'DATA', message: '数据异常' },
        { ...exception, id: 4, err_layer: 'CODE', message: '代码异常' },
      ],
    })

    const page = mountPage(P11Workers)
    await flushPromises()
    await flushPromises()

    const codes = page.findAll('.sp-layer__code').map((node) => node.text())
    expect(codes.slice(0, 4)).toEqual(['UI', 'SYS', 'DATA', 'CODE'])
    expect(page.text()).toContain('暂无在线机器人')
    expect(page.text()).toContain('界面异常')
    expect(page.text()).toContain('可重试')
    expect(page.text()).toContain('E003')
  })
})

describe('P12 权限与订阅', () => {
  it('空订阅使用接口 empty_copy 原文', async () => {
    setRole('OWNER')
    api.fetchIdentityRoles.mockResolvedValue({
      roles: [
        { role: 'OWNER', permissions: ['view_workbench', 'manage_subscriptions'] },
        { role: 'EDITOR', permissions: ['view_workbench'] },
        { role: 'VIEWER', permissions: ['view_workbench'] },
      ],
      shops: [{ platform: 'demo', shop_id: 'SHOP-0001', role: 'OWNER' }],
      note: '',
    })
    api.fetchSubscriptions.mockResolvedValue({
      items: [],
      empty_copy: EMPTY_SUBSCRIPTIONS_COPY,
      channels: ['CONSOLE', 'DINGTALK', 'WECOM', 'EMAIL'],
    })
    api.fetchNotificationTemplates.mockResolvedValue({ items: [] })

    const page = mountPage(P12Access)
    await flushPromises()
    await flushPromises()

    expect(page.text()).toContain(EMPTY_SUBSCRIPTIONS_COPY)
    expect(page.text()).toContain(CREDENTIALS_COPY)
    expect(page.text()).toContain(zhCN.p12.createTitle)
  })

  it('VIEWER 只读时不渲染新建订阅表单与删除按钮', async () => {
    setRole('VIEWER')
    api.fetchIdentityRoles.mockResolvedValue({
      roles: [{ role: 'VIEWER', permissions: ['view_workbench'] }],
      shops: [],
      note: '',
    })
    api.fetchSubscriptions.mockResolvedValue({
      items: [subscription],
      empty_copy: EMPTY_SUBSCRIPTIONS_COPY,
      channels: ['CONSOLE'],
    })
    api.fetchNotificationTemplates.mockResolvedValue({ items: [] })

    const page = mountPage(P12Access)
    await flushPromises()
    await flushPromises()

    expect(page.text()).toContain(zhCN.p12.readonlyHint)
    expect(page.text()).not.toContain(zhCN.p12.createTitle)
    const buttonTexts = page.findAll('button').map((button) => button.text().trim())
    expect(buttonTexts).not.toContain(zhCN.p12.delete)
  })
})

describe('M1 文案红线', () => {
  it('P03 文案树不含自动补货/自动改库存', () => {
    const serialized = JSON.stringify(zhCN)
    expect(serialized).not.toContain('自动补货')
    expect(serialized).not.toContain('自动改库存')
  })

  it('P10 失败文案包含「发布自检未通过」', () => {
    expect(RELEASE_FAILED_COPY).toContain('发布自检未通过')
    expect(zhCN.p10.release.failed).toBe(RELEASE_FAILED_COPY)
  })
})
