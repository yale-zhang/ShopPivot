import type { ReportPayload } from '../src/api/types'

export function makeReport(overrides: Partial<ReportPayload> = {}): ReportPayload {
  return {
    report_id: 'rpt_test0001',
    run_id: 'run_20261125_001',
    platform: 'demo',
    shop_id: 'SHOP-0001',
    window: { start: '2026-11-25', end: '2026-11-25' },
    window_label: '昨日',
    metric_version: 'v1.0',
    watermark: '口径版本 v1.0 · 生成时间 2026-11-25 08:00 · run_id run_20261125_001 · 已脱敏',
    channel: 'BACKEND_EXPORT',
    channel_label: '后台导出',
    generated_at: '2026-11-25T08:00:00+08:00',
    data_state: 'NORMAL',
    empty_copy: '该时间窗暂无数据（非取数失败）',
    columns: [
      {
        key: 'uv',
        label: '访客数 UV',
        unit: '人',
        precision: 0,
        additivity: 'ADDITIVE',
        additivity_label: '可加',
        metric_version: '1.0',
        display_order: 10,
        source: 'dwd_traffic.uv',
        drill: 'metric.uv',
        null_policy: '无数据',
      },
      {
        key: 'cvr',
        label: '转化率',
        unit: '%',
        precision: 2,
        additivity: 'RATIO',
        additivity_label: '不可加（比率类）',
        metric_version: '1.0',
        display_order: 80,
        source: '计算列',
        drill: 'metric.cvr',
        null_policy: '不适用',
      },
    ],
    rows: [
      {
        stat_date: '2026-11-25',
        cells: {
          uv: { value: '12,480', raw: '12480', null_reason: null, metric_code: 'uv' },
          cvr: { value: '9.64', raw: '9.64', null_reason: null, metric_code: 'cvr' },
        },
      },
    ],
    alerts: [],
    readonly: true,
    drill: '指标 → 口径卡 → run_id → ODS 原始证据',
    config_snapshot_hash: '8f13a1c2d3e4f5061728394a5b6c7d8e9f0a1b2c3d4e5f60718293a4b5c6d7e8',
    gate_level_max: 'L0',
    ...overrides,
  }
}

export const emptyReport = (): ReportPayload =>
  makeReport({
    report_id: null,
    run_id: null,
    window: null,
    window_label: '',
    watermark: '',
    channel: null,
    channel_label: '',
    generated_at: null,
    data_state: 'EMPTY',
    empty_copy: '该时间窗暂无数据（非取数失败）',
    columns: [],
    rows: [],
    alerts: [],
  })

export const nullRatioReport = (): ReportPayload =>
  makeReport({
    rows: [
      {
        stat_date: '2026-11-25',
        cells: {
          uv: { value: '12,480', raw: '12480', null_reason: null, metric_code: 'uv' },
          cvr: { value: '分母为零', raw: null, null_reason: '分母为零', metric_code: 'cvr' },
        },
      },
    ],
  })
