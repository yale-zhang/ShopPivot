import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'

import type { AdsSummaryResponse } from '../src/api/types'
import { EMPTY_ADS_COPY, zhCN } from '../src/i18n/zh-CN'
import P04Ads from '../src/pages/P04Ads.vue'

const api = vi.hoisted(() => ({
  fetchAdsSummary: vi.fn(),
}))

vi.mock('../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/client')>()
  return { ...actual, ...api }
})

const NOTE = '只出建议，不自动调价 / 不自动调预算'

function makeSummary(overrides: Partial<AdsSummaryResponse> = {}): AdsSummaryResponse {
  return {
    run_id: 'run-s04-20261125-001',
    window: { start: '2026-11-24', end: '2026-11-25' },
    campaigns: [
      {
        campaign: '秋季拉新',
        cost: 1200,
        revenue: 3600,
        roi: 3,
        alert_level: 'ALERT',
        suggestion: '投产比偏高但花费增速过快，建议人工复核出价与预算',
      },
      {
        campaign: '日常收割',
        cost: 800,
        revenue: 1600,
        roi: 2,
        alert_level: 'OK',
        suggestion: '维持当前出价与预算',
      },
    ],
    counts: { ALERT: 1, OK: 1 },
    totals: { cost: 2000, revenue: 5200, roi: 2.6 },
    note: NOTE,
    empty_copy: EMPTY_ADS_COPY,
    readonly: false,
    ...overrides,
  }
}

let wrapper: VueWrapper | null = null

function mountPage(): VueWrapper {
  wrapper = mount(P04Ads, {
    attachTo: document.body,
    global: { plugins: [createPinia()] },
  })
  return wrapper
}

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

async function mountLoaded(summary: AdsSummaryResponse): Promise<VueWrapper> {
  api.fetchAdsSummary.mockResolvedValue(summary)
  const page = mountPage()
  await flushPromises()
  await flushPromises()
  return page
}

describe('P04 活动与投放', () => {
  it('渲染两个计划、KPI、ALERT 中文「高风险」与常驻 note', async () => {
    const page = await mountLoaded(makeSummary())

    const kpis = page.findAll('.sp-kpi')
    expect(kpis.length).toBe(4)
    expect(kpis[0].text()).toContain(zhCN.p04.kpi.cost)
    expect(kpis[0].text()).toContain('2,000.00')
    expect(kpis[1].text()).toContain(zhCN.p04.kpi.revenue)
    expect(kpis[1].text()).toContain('5,200.00')
    expect(kpis[2].text()).toContain(zhCN.p04.kpi.roi)
    expect(kpis[2].text()).toContain('2.60')
    expect(kpis[3].text()).toContain(zhCN.p04.kpi.alert)
    expect(kpis[3].text()).toContain('1')

    expect(page.findAll('.sp-p04__campaign').length).toBe(2)
    expect(page.text()).toContain('秋季拉新')
    expect(page.text()).toContain('日常收割')
    expect(page.text()).toContain('高风险')
    expect(page.text()).toContain('达标')
    expect(page.text()).toContain('人工复核出价与预算')

    expect(page.find('.sp-p04__note').exists()).toBe(true)
    expect(page.find('.sp-p04__note').text()).toContain(NOTE)

    expect(page.findAll('.sp-p04__bar--cost').length).toBe(2)
    expect(page.findAll('.sp-p04__bar--revenue').length).toBe(2)
    expect(page.text()).not.toContain('一键优化')
  })

  it('空态使用接口 empty_copy 原文，KPI 不显示 0 并常驻 note', async () => {
    const page = await mountLoaded(
      makeSummary({
        campaigns: [],
        counts: {},
        totals: { cost: 0, revenue: 0, roi: null },
        empty_copy: EMPTY_ADS_COPY,
        readonly: true,
      }),
    )

    expect(page.text()).toContain(EMPTY_ADS_COPY)
    const kpiText = page.find('.sp-p04__kpis').text()
    expect(kpiText).toContain(zhCN.common.notAvailable)
    expect(kpiText).not.toMatch(/[0０]/)
    expect(kpiText).not.toContain('1,200.00')

    expect(page.find('.sp-p04__note').text()).toContain(NOTE)
    expect(page.find('.sp-p04__note').exists()).toBe(true)
  })

  it('投产比为 null 显示「不适用」而不是 0', async () => {
    const page = await mountLoaded(
      makeSummary({
        campaigns: [
          {
            campaign: '新客试投',
            cost: 500,
            revenue: 0,
            roi: null,
            alert_level: 'WATCH',
            suggestion: '样本不足，建议继续观察',
          },
        ],
        counts: { WATCH: 1 },
        totals: { cost: 500, revenue: 0, roi: null },
      }),
    )

    expect(page.text()).toContain('关注')
    expect(page.text()).toContain(zhCN.common.notAvailable)
    const roiKpi = page.findAll('.sp-kpi')[2].text()
    expect(roiKpi).toContain(zhCN.common.notAvailable)
    expect(roiKpi).not.toMatch(/[0０]/)
  })
})
