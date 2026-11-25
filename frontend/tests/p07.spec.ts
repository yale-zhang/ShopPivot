import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import { ApiError } from '../src/api/client'
import type {
  ApprovalHistoryItem,
  ApprovalHistoryResponse,
  ChangeOrderPayload,
  PlatformPriceListResponse,
  WritePlanCreateResponse,
} from '../src/api/types'
import { EMPTY_APPROVALS_COPY, READONLY_COPY, zhCN } from '../src/i18n/zh-CN'
import P05Todos from '../src/pages/P05Todos.vue'
import P07Audit from '../src/pages/P07Audit.vue'

const api = vi.hoisted(() => ({
  fetchTodos: vi.fn(),
  fetchPlatformPriceList: vi.fn(),
  createWritePlan: vi.fn(),
  fetchApprovalHistory: vi.fn(),
  fetchAudit: vi.fn(),
  fetchChangeOrder: vi.fn(),
}))

vi.mock('../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/client')>()
  return { ...actual, ...api }
})

const TASK_ID = 'task-m2c-0001'
const AUDIT_AT = '2026-11-25T09:05:00+08:00'

function makeHistoryItem(overrides: Partial<ApprovalHistoryItem> = {}): ApprovalHistoryItem {
  return {
    task_id: TASK_ID,
    change_order_no: 'CO-20261125-0007',
    plan_id: 'wp_m2c_1',
    action_code: 'S02.price_update',
    scene: 'S02',
    platform: 'demo',
    shop_id: 'SHOP-0001',
    status: 'APPROVED',
    plan_status: 'VERIFIED',
    execution_status: 'VERIFIED',
    approver: 'owner',
    requested_by: 'editor',
    rows: 2,
    sla_expires_at: '2026-11-25T10:00:00+08:00',
    created_at: '2026-11-25T09:00:00+08:00',
    ...overrides,
  }
}

function makeHistory(
  items: ApprovalHistoryItem[],
  emptyCopy = EMPTY_APPROVALS_COPY,
): ApprovalHistoryResponse {
  return { items, counts: {}, empty_copy: emptyCopy }
}

function makePriceList(): PlatformPriceListResponse {
  return {
    items: [
      { sku: 'SKU-A', price: '89.00' },
      { sku: 'SKU-B', price: '129.00' },
    ],
    campaign_suggestions: ['C-618', 'C-1111'],
    demo_only: true,
    note: '演示平台价格来自本地受控状态；真实商品清单由平台接口提供',
  }
}

function makeCreatedOrder(): WritePlanCreateResponse {
  return {
    plan: {
      plan_id: 'wp_m2c_new',
      action_code: 'S02.price_update',
      scene: 'S02',
      platform: 'demo',
      shop_id: 'SHOP-0001',
      status: 'PENDING_APPROVAL',
      summary: '商品价格批量维护 · 1 个 SKU',
      impact_scope: '影响 1 个 SKU',
      rollback_plan: '按前值还原',
      plan_hash: 'hash-m2c-new',
      rows: [
        {
          target: 'SKU-A',
          field: 'price',
          before: '89.00',
          after: '79.00',
          impact: 'SKU-A 89.00 → 79.00',
        },
      ],
      evidence: [],
      approval_task_id: 'task-m2c-new',
      execution_id: null,
      error_code: null,
      error_layer: null,
      created_at: '2026-11-25T09:00:00+08:00',
      requested_by: 'editor',
    },
    task_id: 'task-m2c-new',
    sla_expires_at: '2026-11-25T09:30:00+08:00',
  }
}

function makeChangeOrder(): ChangeOrderPayload {
  return {
    change_order_no: 'CO-20261125-0007',
    task_id: TASK_ID,
    plan_id: 'wp_m2c_1',
    status: 'APPROVED',
    plan_status: 'VERIFIED',
    header: {
      scene: 'S02',
      platform: 'demo',
      shop_id: 'SHOP-0001',
      requested_by: 'editor',
      approver: 'owner',
      created_at: '2026-11-25T09:00:00+08:00',
      gate_level: 'L2',
      write_plan_hash: 'hash-m2c-1',
      metric_version: 'v1.0',
      snapshot_time: '2026-11-25T08:00:00+08:00',
      schema_version: '1.0',
      sla_expires_at: '2026-11-25T10:00:00+08:00',
    },
    before_after: [
      {
        target: 'SKU-A',
        field: 'price',
        before: '89.00',
        after: '79.00',
        impact: 'SKU-A 89.00 → 79.00',
      },
    ],
    impact_scope: '影响 1 个 SKU 的前台售价',
    evidence: [{ kind: 'snapshot', ref: 'shot://before/S02/SKU-A', label: '变更前页面快照' }],
    rollback_plan: '恢复为 89.00',
    evidence_complete: true,
    readonly: true,
    can_approve: false,
    readonly_copy: READONLY_COPY,
    execution: {
      execution_id: 'exec_m2c_1',
      status: 'VERIFIED',
      before_shot: 'shot://before/wp_m2c_1',
      after_shot: 'shot://after/wp_m2c_1',
      verify_result: { verified: true, checked_rows: 1 },
      err_code: null,
      err_layer: null,
      ended_at: '2026-11-25T09:06:00+08:00',
    },
    result_timeline: [{ state: 'APPROVED', at: '2026-11-25T09:05:00+08:00', label: '已批准' }],
  }
}

let wrapper: VueWrapper | null = null
let router: Router | null = null

function setRole(role: string): void {
  localStorage.clear()
  localStorage.setItem('shoppivot.token', 'test-token')
  localStorage.setItem('shoppivot.role', role)
}

function makeRouter(): Router {
  const created = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/p05', component: P05Todos },
      { path: '/p07', component: P07Audit },
      { path: '/change-orders/:id', component: { template: '<div class="route-stub" />' } },
    ],
  })
  return created
}

async function mountAt(path: string, component: unknown): Promise<VueWrapper> {
  router = makeRouter()
  await router.push(path)
  await router.isReady()
  wrapper = mount(component as never, {
    attachTo: document.body,
    global: { plugins: [createPinia(), router] },
  })
  await flushPromises()
  await flushPromises()
  return wrapper
}

function queryElement<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector)
  expect(element).not.toBeNull()
  return element as T
}

function setSelect(selector: string, value: string): void {
  const element = queryElement<HTMLSelectElement>(selector)
  element.value = value
  element.dispatchEvent(new Event('change'))
}

function setInput(selector: string, value: string): void {
  const element = queryElement<HTMLInputElement>(selector)
  element.value = value
  element.dispatchEvent(new Event('input'))
}

beforeEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
  api.fetchTodos.mockResolvedValue({ items: [], counts: {}, readonly: false })
  api.fetchPlatformPriceList.mockResolvedValue(makePriceList())
  api.createWritePlan.mockResolvedValue(makeCreatedOrder())
  api.fetchApprovalHistory.mockResolvedValue(makeHistory([makeHistoryItem()]))
  api.fetchAudit.mockResolvedValue({ items: [], filters: {} })
  api.fetchChangeOrder.mockResolvedValue(makeChangeOrder())
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  router = null
  document.body.innerHTML = ''
  localStorage.clear()
})

describe('P07 审批记录与审计', () => {
  it('渲染审批历史列表：变更单号、动作、审批人与状态徽标', async () => {
    setRole('OWNER')

    const page = await mountAt('/p07', P07Audit)

    expect(api.fetchApprovalHistory).toHaveBeenCalledTimes(1)
    expect(api.fetchApprovalHistory).toHaveBeenCalledWith({
      limit: 100,
      status: '',
      actionCode: '',
      approver: '',
    })

    const text = page.text()
    expect(text).toContain('CO-20261125-0007')
    expect(text).toContain('S02.price_update')
    expect(text).toContain(zhCN.p07.actionLabels['S02.price_update'])
    expect(text).toContain('owner')
    expect(text).toContain(zhCN.statusLabel.APPROVED)
    expect(text).toContain(zhCN.statusLabel.VERIFIED)

    const badges = page.findAll('.sp-status-tag')
    expect(badges.length).toBeGreaterThanOrEqual(2)
    expect(badges.some((badge) => badge.text().includes(zhCN.statusLabel.APPROVED))).toBe(true)
  })

  it('点击行打开抽屉：拉取审计时间线并展示 action / actor', async () => {
    setRole('OWNER')
    api.fetchAudit.mockResolvedValue({
      items: [
        {
          id: 1,
          at: AUDIT_AT,
          actor: 'owner',
          action: 'write_plan.approve',
          object_type: 'write_plan',
          object_id: 'wp_m2c_1',
          reason: '核对无误，批准执行',
          before: null,
          after: null,
          ip: null,
          result: 'OK',
        },
      ],
      filters: {},
    })

    const page = await mountAt('/p07', P07Audit)
    const tableRow = page.find('.el-table__row')
    expect(tableRow.exists()).toBe(true)
    await tableRow.trigger('click')
    await flushPromises()
    await flushPromises()
    await flushPromises()

    expect(api.fetchAudit).toHaveBeenCalledWith({ objectId: 'wp_m2c_1', limit: 100 })
    expect(api.fetchChangeOrder).toHaveBeenCalledWith(TASK_ID)

    const text = document.body.textContent ?? ''
    expect(text).toContain(zhCN.p07.drawer.title)
    expect(text).toContain(zhCN.p07.drawer.audit)
    expect(text).toContain('write_plan.approve')
    expect(text).toContain('owner')
    expect(text).toContain('核对无误，批准执行')
    expect(text).toContain(zhCN.p07.drawer.openP06)
    expect(text).toContain('shot://before/S02/SKU-A')
  })

  it('空态使用接口返回的 empty_copy 原文', async () => {
    setRole('OWNER')
    api.fetchApprovalHistory.mockResolvedValue(makeHistory([], EMPTY_APPROVALS_COPY))

    const page = await mountAt('/p07', P07Audit)

    expect(page.text()).toContain(EMPTY_APPROVALS_COPY)
    expect(page.text()).toContain(zhCN.p07.emptyHint)
    expect(page.find('.el-table__row').exists()).toBe(false)
  })

  it('接口 403 时展示无权限提示而不是空态', async () => {
    setRole('EDITOR')
    api.fetchApprovalHistory.mockRejectedValue(
      new ApiError({
        code: 'E004',
        layer: 'AUTH',
        userMessage: zhCN.p07.forbidden,
        status: 403,
      }),
    )

    const page = await mountAt('/p07', P07Audit)

    expect(page.text()).toContain(zhCN.p07.forbidden)
    expect(page.text()).toContain(zhCN.p07.forbiddenHint)
    expect(page.text()).not.toContain(EMPTY_APPROVALS_COPY)
  })
})

describe('P05 新建变更单', () => {
  it('S02 未填目标价时不发请求；填好后 POST /write-plans 并跳转变更单详情', async () => {
    setRole('EDITOR')

    const page = await mountAt('/p05', P05Todos)

    const createButton = queryElement<HTMLButtonElement>('[data-action="create-change-order"]')
    createButton.click()
    await flushPromises()
    await flushPromises()

    expect(document.body.textContent).toContain(zhCN.p05.create.title)

    setSelect('[data-field="sku"]', 'SKU-A')

    const submit = queryElement<HTMLButtonElement>('[data-action="submit-create-order"]')
    submit.click()
    await flushPromises()

    expect(api.createWritePlan).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(zhCN.p05.create.priceRequired)

    setInput('[data-field="after"]', '79.00')
    submit.click()
    await flushPromises()
    await flushPromises()
    await flushPromises()

    expect(api.createWritePlan).toHaveBeenCalledTimes(1)
    const payload = api.createWritePlan.mock.calls[0][0] as {
      action_code: string
      platform: string
      shop_id: string
      rows: Array<{ sku: string; after: string }>
      idempotency_key: string
    }
    expect(payload.action_code).toBe('S02.price_update')
    expect(payload.platform).toBe('demo')
    expect(payload.shop_id).toBe('SHOP-0001')
    expect(payload.rows).toEqual([{ sku: 'SKU-A', after: '79.00' }])
    expect(payload.idempotency_key).toMatch(/^ui-S02-\d+$/)

    expect(router?.currentRoute.value.path).toBe('/change-orders/task-m2c-new')
    expect(api.fetchTodos).toHaveBeenCalledTimes(2)
    expect(page.text()).toContain(zhCN.p05.title)
  })

  it('S03 活动提报提交 campaign_id / sku / activity_price', async () => {
    setRole('EDITOR')

    await mountAt('/p05', P05Todos)

    queryElement<HTMLButtonElement>('[data-action="create-change-order"]').click()
    await flushPromises()
    await flushPromises()

    setSelect('[data-field="action_code"]', 'S03.campaign_apply')
    await flushPromises()

    const suggestion = Array.from(
      document.querySelectorAll<HTMLButtonElement>('.sp-create__suggestions button'),
    ).find((button) => (button.textContent ?? '').trim() === 'C-618')
    expect(suggestion).toBeTruthy()
    suggestion?.click()

    setSelect('[data-field="sku"]', 'SKU-B')
    setInput('[data-field="activity_price"]', '99.00')

    queryElement<HTMLButtonElement>('[data-action="submit-create-order"]').click()
    await flushPromises()
    await flushPromises()
    await flushPromises()

    expect(api.createWritePlan).toHaveBeenCalledTimes(1)
    const payload = api.createWritePlan.mock.calls[0][0] as {
      action_code: string
      rows: Array<{ campaign_id: string; sku: string; activity_price: string }>
      idempotency_key: string
    }
    expect(payload.action_code).toBe('S03.campaign_apply')
    expect(payload.rows).toEqual([
      { campaign_id: 'C-618', sku: 'SKU-B', activity_price: '99.00' },
    ])
    expect(payload.idempotency_key).toMatch(/^ui-S03-\d+$/)
  })

  it('VIEWER 不显示「新建变更单」按钮', async () => {
    setRole('VIEWER')

    await mountAt('/p05', P05Todos)

    expect(document.querySelector('[data-action="create-change-order"]')).toBeNull()
  })
})
