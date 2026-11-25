import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'

import type { SettlementReconciliationResponse } from '../src/api/types'
import { EMPTY_SETTLEMENT_COPY, zhCN } from '../src/i18n/zh-CN'
import P08Reconciliation from '../src/pages/P08Reconciliation.vue'

const api = vi.hoisted(() => ({
  fetchSettlementReconciliation: vi.fn(),
}))

vi.mock('../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/client')>()
  return { ...actual, ...api }
})

const NOTE = '财务写入禁止（L3）；差异逐条可追溯双边凭据'

function makeReconciliation(
  overrides: Partial<SettlementReconciliationResponse> = {},
): SettlementReconciliationResponse {
  return {
    run_id: 'run-s09-20261125-001',
    window: { start: '2026-11-01', end: '2026-11-25' },
    diffs: [
      {
        order_id: 'D0-1001',
        expected_net: 500,
        settled_amount: 500,
        commission: 50,
        delta: 0,
        diff_type: 'MATCH',
        order_ref: 'orders.csv#D0-1001',
        settlement_ref: 'settlement.csv#S0-1001',
        status: 'OPEN',
      },
      {
        order_id: 'D0-1002',
        expected_net: 717,
        settled_amount: 700,
        commission: 33,
        delta: -17,
        diff_type: 'AMOUNT_DIFF',
        order_ref: 'orders.csv#D0-1002',
        settlement_ref: 'settlement.csv#S0-1002',
        status: 'OPEN',
      },
      {
        order_id: 'D0-1003',
        expected_net: 300,
        settled_amount: null,
        commission: null,
        delta: -300,
        diff_type: 'MISSING_SETTLEMENT',
        order_ref: 'orders.csv#D0-1003',
        settlement_ref: '',
        status: 'OPEN',
      },
      {
        order_id: 'D9-9999',
        expected_net: 0,
        settled_amount: 250,
        commission: 20,
        delta: 250,
        diff_type: 'MISSING_ORDER',
        order_ref: '',
        settlement_ref: 'settlement.csv#S9-9999',
        status: 'OPEN',
      },
    ],
    counts: { MATCH: 1, AMOUNT_DIFF: 1, MISSING_SETTLEMENT: 1, MISSING_ORDER: 1 },
    totals: { expected: 1517, settled: 1450, delta: -67 },
    note: NOTE,
    empty_copy: EMPTY_SETTLEMENT_COPY,
    readonly: true,
    ...overrides,
  }
}

let wrapper: VueWrapper | null = null

beforeEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  localStorage.clear()
})

async function mountLoaded(
  payload: SettlementReconciliationResponse,
): Promise<VueWrapper> {
  api.fetchSettlementReconciliation.mockResolvedValue(payload)
  wrapper = mount(P08Reconciliation, { attachTo: document.body })
  await flushPromises()
  await flushPromises()
  return wrapper
}

describe('P08 对账与差异', () => {
  it('渲染 4 条差异、类型中文、totals 与常驻 note', async () => {
    const page = await mountLoaded(makeReconciliation())

    expect(api.fetchSettlementReconciliation).toHaveBeenCalledTimes(1)

    const kpis = page.findAll('.sp-kpi')
    expect(kpis.length).toBe(4)
    expect(kpis[0].text()).toContain(zhCN.p08.kpi.expected)
    expect(kpis[0].text()).toContain('1,517.00')
    expect(kpis[1].text()).toContain(zhCN.p08.kpi.settled)
    expect(kpis[1].text()).toContain('1,450.00')
    expect(kpis[2].text()).toContain(zhCN.p08.kpi.delta)
    expect(kpis[2].text()).toContain('-67.00')
    expect(kpis[3].text()).toContain(zhCN.p08.kpi.diffs)
    expect(kpis[3].text()).toContain('3')

    expect(page.findAll('.el-table__row').length).toBe(4)
    expect(page.text()).toContain('D0-1001')
    expect(page.text()).toContain('D9-9999')
    expect(page.text()).toContain('一致')
    expect(page.text()).toContain('金额差异')
    expect(page.text()).toContain('缺结算单')
    expect(page.text()).toContain('缺订单')
    expect(page.text()).toContain('settlement.csv#S0-1002')
    expect(page.text()).toContain('orders.csv#D0-1003')

    expect(page.find('.sp-p08__note').exists()).toBe(true)
    expect(page.find('.sp-p08__note').text()).toContain(NOTE)
    expect(page.text()).toContain(zhCN.p08.financeWriteForbidden)

    const text = page.text()
    expect(text).not.toContain('自动对账写入')
    expect(text).not.toContain('财务回写')
    expect(text).not.toContain('一键平账')
    expect(text).not.toContain('财务确认')
  })

  it('空态使用 empty_copy 原文，KPI 不显示 0 冒充', async () => {
    const page = await mountLoaded(
      makeReconciliation({
        run_id: null,
        window: null,
        diffs: [],
        counts: {},
        totals: { expected: 0, settled: 0, delta: 0 },
        empty_copy: EMPTY_SETTLEMENT_COPY,
      }),
    )

    expect(page.text()).toContain(EMPTY_SETTLEMENT_COPY)
    expect(page.text()).toContain(zhCN.p08.emptyHint)

    const kpiText = page.find('.sp-p08__kpis').text()
    expect(kpiText).toContain(zhCN.common.none)
    expect(kpiText).not.toMatch(/[0０]/)

    expect(page.find('.el-table__row').exists()).toBe(false)
    expect(page.find('.sp-p08__note').text()).toContain(NOTE)
  })

  it('类型过滤只显示对应行，并可恢复全部', async () => {
    const page = await mountLoaded(makeReconciliation())

    await page.find('[data-filter="AMOUNT_DIFF"]').trigger('click')
    await flushPromises()

    let rows = page.findAll('.el-table__row')
    expect(rows.length).toBe(1)
    expect(rows[0].text()).toContain('D0-1002')
    expect(page.text()).not.toContain('D0-1001')
    expect(page.text()).not.toContain('D9-9999')

    await page.find('[data-filter="ALL"]').trigger('click')
    await flushPromises()
    rows = page.findAll('.el-table__row')
    expect(rows.length).toBe(4)
  })

  it('点击行抽屉展示 refs、status 与账期 totals 上下文', async () => {
    const page = await mountLoaded(makeReconciliation())

    const row = page
      .findAll('.el-table__row')
      .find((item) => item.text().includes('D0-1002'))
    expect(row).toBeTruthy()
    await row?.trigger('click')
    await flushPromises()

    const text = document.body.textContent ?? ''
    expect(text).toContain(zhCN.p08.drawer.title)
    expect(text).toContain(zhCN.p08.drawer.summary)
    expect(text).toContain(zhCN.p08.drawer.totals)
    expect(text).toContain('待人工认定')
    expect(text).toContain('orders.csv#D0-1002')
    expect(text).toContain('settlement.csv#S0-1002')
    expect(text).toContain('-17.00')
    expect(text).toContain(zhCN.p08.drawer.note)
    expect(text).not.toContain('财务确认')
    expect(text).not.toContain('一键平账')
  })
})
