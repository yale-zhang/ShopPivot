import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import {
  EMPTY_REPORT_COPY,
  EMPTY_TODOS_COPY,
  EXPIRED_COPY,
  MASKED_COPY,
  RATIO_BADGE,
  READONLY_COPY,
  UNAVAILABLE_PAGE_COPY,
  moduleBlockedCopy,
  zhCN,
} from '../src/i18n/zh-CN'
import CountdownBadge from '../src/components/CountdownBadge.vue'
import MetricCard from '../src/components/MetricCard.vue'
import StateView from '../src/components/StateView.vue'

describe('中文文案红线', () => {
  it('空态使用规定原文且不含数字 0', () => {
    expect(EMPTY_REPORT_COPY).toBe('该时间窗暂无数据（非取数失败）')
    expect(EMPTY_REPORT_COPY).not.toMatch(/[0０]/)
    expect(zhCN.p05.empty).toBe(EMPTY_TODOS_COPY)

    const wrapper = mount(StateView, { props: { state: 'empty' } })
    expect(wrapper.text()).toContain(EMPTY_REPORT_COPY)
    expect(wrapper.text()).not.toMatch(/[0０]/)
  })

  it('比率合计标记固定为「不可加（比率类）」', () => {
    expect(RATIO_BADGE).toBe('不可加（比率类）')
    expect(zhCN.p01.ratioBadge).toBe(RATIO_BADGE)
    expect(zhCN.drill.additivityLabels.RATIO).toBe(RATIO_BADGE)
  })

  it('只读、超时作废、脱敏、后续阶段提示均使用规定原文', () => {
    expect(READONLY_COPY).toBe('需审批后执行（当前只读模式）')
    expect(EXPIRED_COPY).toBe('已超时自动作废，需重新发起变更单')
    expect(MASKED_COPY).toBe('买家信息已脱敏，原文证据仅审计角色可见')
    expect(UNAVAILABLE_PAGE_COPY).toBe('该页面在后续阶段交付')
    expect(zhCN.p06.actions.readonly).toBe(READONLY_COPY)
    expect(zhCN.components.countdown.expired).toBe(EXPIRED_COPY)
    expect(zhCN.evidence.masked).toBe(MASKED_COPY)
  })

  it('模块阻断文案包含模块名与原因', () => {
    const copy = moduleBlockedCopy('mod_worker_headless', '循环依赖：api_compat 不匹配')
    expect(copy).toBe('模块 mod_worker_headless 未加载：循环依赖：api_compat 不匹配')
    expect(copy).toContain('mod_worker_headless')
    expect(zhCN.p09.blockedLine('mod_x', 'gate_level_max=L2 越权')).toContain('模块 mod_x 未加载：')
  })

  it('不存在自动化执行的越权文案', () => {
    const serialized = JSON.stringify(zhCN)
    expect(serialized).not.toContain('AI 自动执行')
    expect(serialized).not.toContain('一键优化')
    expect(serialized).not.toContain('已自动执行')
  })

  it('空值指标不渲染为 0，而显示「不适用」', () => {
    const wrapper = mount(MetricCard, {
      props: {
        metricCode: 'cvr',
        label: '转化率',
        value: null,
        unit: '%',
        nullReason: '分母为零',
        latestDate: '2026-11-25',
      },
    })
    expect(wrapper.text()).toContain('不适用')
    expect(wrapper.text()).toContain('原因：分母为零')
    expect(wrapper.text()).not.toMatch(/\b0(\.0+)?\b/)
  })

  it('超时倒计时显示「已超时」，作废显示灰态文案', () => {
    const overdue = mount(CountdownBadge, {
      props: { remainingSeconds: -12, status: 'PENDING', overdue: true },
    })
    expect(overdue.text()).toContain('已超时')

    const expired = mount(CountdownBadge, {
      props: { remainingSeconds: -12, status: 'EXPIRED' },
    })
    expect(expired.text()).toContain(EXPIRED_COPY)
  })
})
