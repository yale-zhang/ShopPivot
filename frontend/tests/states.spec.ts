import { describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import { EMPTY_REPORT_COPY, READONLY_COPY, zhCN } from '../src/i18n/zh-CN'
import ApprovalActions from '../src/components/ApprovalActions.vue'
import BlockingAlert from '../src/components/BlockingAlert.vue'
import DataTable from '../src/components/DataTable.vue'
import EvidencePack from '../src/components/EvidencePack.vue'
import { emptyReport, makeReport, nullRatioReport } from './fixtures'

describe('P01 日报表', () => {
  it('比率列展示「不可加（比率类）」表头徽标', async () => {
    const wrapper = mount(DataTable, { props: { report: makeReport() } })
    await flushPromises()
    expect(wrapper.text()).toContain('不可加（比率类）')
    expect(wrapper.text()).toContain('单位：%')
  })

  it('分母为零的单元格显示「不适用」而不是 0', async () => {
    const wrapper = mount(DataTable, { props: { report: nullRatioReport() } })
    await flushPromises()
    const nullCells = wrapper.findAll('.sp-cell.is-null')
    expect(nullCells.length).toBeGreaterThan(0)
    expect(nullCells[0].text()).toBe('不适用')
  })

  it('空报表展示规定空态原文且不含 0', async () => {
    const wrapper = mount(DataTable, { props: { report: emptyReport() } })
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain(EMPTY_REPORT_COPY)
    expect(text).not.toMatch(/[0０]/)
  })
})

describe('P06 只读审批', () => {
  it('只读时四个操作按钮全部 disabled，并显示 readonly_copy 原文', () => {
    const wrapper = mount(ApprovalActions, {
      props: { readonly: true, readonlyCopy: READONLY_COPY },
    })
    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(4)
    for (const button of buttons) {
      expect(button.attributes('disabled')).toBeDefined()
    }
    expect(wrapper.text()).toContain(READONLY_COPY)
    expect(wrapper.text()).not.toContain('已自动执行')
  })

  it('证据不完整时红字提示禁止批准', () => {
    const wrapper = mount(EvidencePack, {
      props: {
        items: [{ kind: 'metric_card', ref: 'metric.cvr@1.0', label: '口径卡引用' }],
        complete: false,
      },
    })
    expect(wrapper.text()).toContain('证据缺失，禁止批准')
  })
})

describe('P09 模块阻断', () => {
  it('阻断区域逐条包含模块名和原因', () => {
    const wrapper = mount(BlockingAlert, {
      props: {
        blocked: [
          {
            module: 'mod_worker_headless',
            check: 'api_compat',
            reason: 'gate_level_max=L2 越权',
          },
        ],
      },
    })
    expect(wrapper.text()).toContain('模块 mod_worker_headless 未加载：gate_level_max=L2 越权')
    expect(wrapper.text()).toContain('mod_worker_headless')
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.text()).toContain(zhCN.p09.blockedTitle)
  })
})
