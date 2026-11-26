import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import type {
  PurchaseOrder,
  PurchasesResponse,
  SourcingCandidate,
  SourcingProviderResponse,
  SourcingSearchResponse,
  WritePlanCreateResponse,
} from '../src/api/types'
import {
  EMPTY_CANDIDATES_COPY,
  EMPTY_PURCHASES_COPY,
  SOURCING_BOUNDARY_COPY,
  zhCN,
} from '../src/i18n/zh-CN'
import P13Sourcing from '../src/pages/P13Sourcing.vue'

const api = vi.hoisted(() => ({
  searchSourcing: vi.fn(),
  fetchSourcingCandidates: vi.fn(),
  fetchSourcingCandidate: vi.fn(),
  fetchSourcingProvider: vi.fn(),
  fetchPurchases: vi.fn(),
  refreshPurchase: vi.fn(),
  createPurchasePlan: vi.fn(),
}))

vi.mock('../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/client')>()
  return { ...actual, ...api }
})

const PROVIDER_NOTE = '选品可自动；下单只创建 checkout，支付必须由人在 1688/UTP 收银台完成'
const REFRESH_NOTE = '支付状态来自 1688/UTP 回读；本系统不代付'
const CONTINUE_URL = 'https://utp.example.com/checkout/co_p13_1'

function makeProvider(overrides: Partial<SourcingProviderResponse> = {}): SourcingProviderResponse {
  return {
    mode: 'mock',
    sourcing_provider: 'mock-1688',
    purchase_provider: 'mock-utp',
    note: PROVIDER_NOTE,
    ...overrides,
  }
}

function makeCandidate(overrides: Partial<SourcingCandidate> = {}): SourcingCandidate {
  return {
    run_id: 'run-s10-20261126-001',
    keyword: '垃圾袋',
    offer_id: 'offer-1',
    title: '加厚黑色垃圾袋 45×50',
    price: 3.2,
    post_fee: 0,
    moq: 2,
    sales_30d: 1200,
    supplier: '义乌日用百货',
    pic_url: '',
    url: 'https://detail.1688.com/offer/1.html',
    brand_authorized: true,
    score: 87.5,
    rank: 1,
    risk_flags: [],
    risk_label: '—',
    ...overrides,
  }
}

function makeSearch(
  candidates: SourcingCandidate[],
  overrides: Partial<SourcingSearchResponse> = {},
): SourcingSearchResponse {
  return {
    run_id: 'run-s10-20261126-001',
    status: 'SUCCEEDED',
    keyword: '垃圾袋',
    candidates,
    count: candidates.length,
    empty_copy: EMPTY_CANDIDATES_COPY,
    provider: 'mock-1688',
    ...overrides,
  }
}

function makeOrder(overrides: Partial<PurchaseOrder> = {}): PurchaseOrder {
  return {
    plan_id: 'wp_p13_0001',
    provider: 'mock-utp',
    items: [
      {
        offer_id: 'offer-1',
        title: '加厚黑色垃圾袋 45×50',
        quantity: 6,
        unit_price: 3.2,
        post_fee: 0,
        spec_id: '',
        subtotal: 19.2,
      },
    ],
    total: 19.2,
    quantity: 6,
    checkout_id: 'co_p13_1',
    status: 'AWAITING_PAYMENT',
    status_label: '待支付',
    continue_url: CONTINUE_URL,
    buyer_note: '',
    created_at: '2026-11-26T10:00:00+08:00',
    updated_at: '2026-11-26T10:01:00+08:00',
    task_id: 'task-p13-1',
    ...overrides,
  }
}

function makePurchases(items: PurchaseOrder[]): PurchasesResponse {
  return { items, empty_copy: EMPTY_PURCHASES_COPY, readonly: true }
}

function makeCreatedOrder(): WritePlanCreateResponse {
  return {
    plan: {
      plan_id: 'wp_p13_plan_1',
      action_code: 'S11.purchase_order',
      scene: 'S11',
      platform: 'demo',
      shop_id: 'SHOP-0001',
      status: 'PENDING_APPROVAL',
      summary: '采购 6 件垃圾袋',
      impact_scope: '只创建 checkout，不支付',
      rollback_plan: '取消 checkout',
      plan_hash: 'a1b2c3d4',
      rows: [],
      evidence: [],
      approval_task_id: 'task-p13-1',
      execution_id: null,
      error_code: null,
      error_layer: null,
      created_at: '2026-11-26T10:00:00+08:00',
      requested_by: 'editor',
    },
    task_id: 'task-p13-1',
    sla_expires_at: '2026-11-26T11:00:00+08:00',
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
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/p13', component: P13Sourcing },
      { path: '/change-orders/:id', component: { template: '<div class="route-stub" />' } },
    ],
  })
}

async function mountPage(): Promise<VueWrapper> {
  router = makeRouter()
  await router.push('/p13')
  await router.isReady()
  wrapper = mount(P13Sourcing, {
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

function setInput(selector: string, value: string): void {
  const element = queryElement<HTMLInputElement>(selector)
  element.value = value
  element.dispatchEvent(new Event('input'))
}

async function performSearch(keyword = '垃圾袋'): Promise<void> {
  setInput('[data-field="sourcing-keyword"]', keyword)
  queryElement<HTMLButtonElement>('[data-action="sourcing-search"]').click()
  await flushPromises()
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
  localStorage.clear()
  api.fetchSourcingProvider.mockResolvedValue(makeProvider())
  api.fetchPurchases.mockResolvedValue(makePurchases([]))
  api.searchSourcing.mockResolvedValue(makeSearch([]))
  api.createPurchasePlan.mockResolvedValue(makeCreatedOrder())
  api.refreshPurchase.mockResolvedValue({
    ...makeOrder(),
    status: 'PAID',
    status_label: '已支付',
    continue_url: '',
    note: REFRESH_NOTE,
  })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  router = null
  document.body.innerHTML = ''
  localStorage.clear()
})

describe('P13 1688 选品与采购', () => {
  it('搜索成功后渲染候选、评分、风险标签（品牌未授权）与 provider 提示', async () => {
    setRole('EDITOR')
    api.searchSourcing.mockResolvedValue(
      makeSearch([
        makeCandidate({ offer_id: 'offer-1', rank: 1, score: 92.5, risk_flags: ['需邮费'], post_fee: 3 }),
        makeCandidate({
          offer_id: 'offer-2',
          rank: 2,
          title: '可降解垃圾袋 30×40',
          supplier: '宁波环保制品',
          brand_authorized: false,
          price: 4.5,
          moq: 5,
          score: 61.25,
          risk_flags: ['品牌未授权'],
        }),
      ]),
    )

    const page = await mountPage()

    expect(page.find('[data-p13="provider"]').text()).toContain(zhCN.p13.humanLoop)
    expect(page.find('[data-p13="provider"]').text()).toContain(PROVIDER_NOTE)
    expect(page.find('[data-p13="boundary"]').text()).toContain(SOURCING_BOUNDARY_COPY)

    await performSearch()

    expect(api.searchSourcing).toHaveBeenCalledWith({
      keyword: '垃圾袋',
      limit: 20,
      filters: [],
    })
    expect(page.text()).toContain('加厚黑色垃圾袋 45×50')
    expect(page.text()).toContain('宁波环保制品')
    expect(page.text()).toContain('92.50')
    expect(page.text()).toContain('61.25')
    expect(page.text()).toContain(zhCN.p13.riskLabels['需邮费'])

    const brandChip = page.find('.sp-p13__risk--danger')
    expect(brandChip.exists()).toBe(true)
    expect(brandChip.text()).toContain(zhCN.p13.riskBrandFlag)
    expect(page.find('[data-p13="candidates"]').text()).toContain('义乌日用百货')

    expect(page.text()).not.toContain('一键自动下单')
    expect(page.text()).not.toContain('自动支付')
    expect(page.text()).not.toContain('免确认下单')
  })

  it('候选空态使用接口 empty_copy 原文', async () => {
    setRole('EDITOR')
    const apiEmptyCopy = '该关键词暂无候选货源（接口原文）'
    api.searchSourcing.mockResolvedValue(makeSearch([], { empty_copy: apiEmptyCopy }))

    const page = await mountPage()
    await performSearch('不存在的关键词')

    expect(page.text()).toContain(apiEmptyCopy)
    expect(page.text()).toContain(zhCN.p13.candidates.emptyHint)
    expect(page.findAll('.sp-p13__offer').length).toBe(0)
  })

  it('选中候选填数量后调用 /write-plans 并跳转（数量不得低于起订量）', async () => {
    setRole('EDITOR')
    api.searchSourcing.mockResolvedValue(
      makeSearch([makeCandidate({ offer_id: 'offer-7', moq: 3, price: 3.2, post_fee: 1 })]),
    )

    const page = await mountPage()
    await performSearch()

    queryElement<HTMLButtonElement>('[data-select-offer="offer-7"]').click()
    await flushPromises()

    const quantity = queryElement<HTMLInputElement>('[data-field="purchase-quantity"]')
    expect(quantity.value).toBe('3')

    setInput('[data-field="purchase-quantity"]', '1')
    queryElement<HTMLButtonElement>('[data-action="create-purchase-order"]').click()
    await flushPromises()

    expect(api.createPurchasePlan).not.toHaveBeenCalled()
    expect(page.text()).toContain(zhCN.p13.purchase.quantityInvalid(3))

    setInput('[data-field="purchase-quantity"]', '6')
    queryElement<HTMLButtonElement>('[data-action="create-purchase-order"]').click()
    await flushPromises()
    await flushPromises()
    await flushPromises()

    expect(api.createPurchasePlan).toHaveBeenCalledTimes(1)
    const payload = api.createPurchasePlan.mock.calls[0][0] as {
      action_code: string
      platform: string
      shop_id: string
      rows: Array<{ offer_id: string; quantity: number }>
      idempotency_key: string
      scene: string
    }
    expect(payload.action_code).toBe('S11.purchase_order')
    expect(payload.platform).toBe('demo')
    expect(payload.shop_id).toBe('SHOP-0001')
    expect(payload.rows).toEqual([{ offer_id: 'offer-7', quantity: 6 }])
    expect(payload.idempotency_key).toMatch(/^ui-p13-\d+$/)
    expect(payload.scene).toBe('S11')
    expect(router?.currentRoute.value.path).toBe('/change-orders/task-p13-1')
  })

  it('采购单列表渲染待支付、continue_url 外链与刷新按钮，刷新后更新为已支付', async () => {
    setRole('OWNER')
    api.fetchPurchases.mockResolvedValue(makePurchases([makeOrder()]))

    const page = await mountPage()

    expect(page.text()).toContain(zhCN.p13.purchaseStatus.AWAITING_PAYMENT)

    const link = queryElement<HTMLAnchorElement>('[data-p13="purchase-continue"]')
    expect(link.getAttribute('href')).toBe(CONTINUE_URL)
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toBe('noopener')

    const refresh = queryElement<HTMLButtonElement>('[data-action="refresh-purchase"]')
    expect(refresh.getAttribute('data-plan-id')).toBe('wp_p13_0001')
    refresh.click()
    await flushPromises()
    await flushPromises()

    expect(api.refreshPurchase).toHaveBeenCalledWith('wp_p13_0001')
    expect(page.text()).toContain(zhCN.p13.purchaseStatus.PAID)
    expect(document.querySelector('[data-p13="purchase-continue"]')).toBeNull()
    expect(page.text()).toContain(REFRESH_NOTE)
  })

  it('采购单空态使用接口 empty_copy「暂无采购单」', async () => {
    setRole('VIEWER')
    api.fetchPurchases.mockResolvedValue(makePurchases([]))

    const page = await mountPage()

    expect(EMPTY_PURCHASES_COPY).toBe('暂无采购单')
    const orders = page.find('[data-p13="purchase-orders"]')
    expect(orders.text()).toContain(EMPTY_PURCHASES_COPY)
    expect(orders.text()).toContain(zhCN.p13.orders.emptyHint)
  })

  it('VIEWER 不显示创建采购单入口', async () => {
    setRole('VIEWER')
    api.searchSourcing.mockResolvedValue(makeSearch([makeCandidate({ offer_id: 'offer-1' })]))

    const page = await mountPage()
    await performSearch()

    queryElement<HTMLButtonElement>('[data-select-offer="offer-1"]').click()
    await flushPromises()

    expect(document.querySelector('[data-action="create-purchase-order"]')).toBeNull()
    expect(document.querySelector('[data-field="purchase-quantity"]')).toBeNull()
    expect(page.text()).toContain(zhCN.p13.purchase.viewerHint)
  })
})
