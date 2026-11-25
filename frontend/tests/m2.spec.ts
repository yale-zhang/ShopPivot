import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import type { ChangeOrderPayload } from '../src/api/types'
import { READONLY_COPY, zhCN } from '../src/i18n/zh-CN'
import { formatDateTime } from '../src/utils/format'
import P06ChangeOrder from '../src/pages/P06ChangeOrder.vue'

const api = vi.hoisted(() => ({
  fetchChangeOrder: vi.fn(),
  approveWritePlan: vi.fn(),
  rejectWritePlan: vi.fn(),
  withdrawWritePlan: vi.fn(),
  compensateWritePlan: vi.fn(),
  transferChangeOrder: vi.fn(),
}))

vi.mock('../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/api/client')>()
  return { ...actual, ...api }
})

const ORDER_NO = 'CO-20261125-0001'

function makeChangeOrder(overrides: Partial<ChangeOrderPayload> = {}): ChangeOrderPayload {
  return {
    change_order_no: ORDER_NO,
    task_id: 'task-m2-1',
    plan_id: 'wp_m2_1',
    status: 'PENDING',
    plan_status: 'PENDING_APPROVAL',
    header: {
      scene: 'S02',
      platform: 'demo',
      shop_id: 'SHOP-0001',
      requested_by: 'editor',
      approver: 'owner',
      created_at: '2026-11-25T09:00:00+08:00',
      gate_level: 'L2',
      write_plan_hash: 'a1b2c3d4e5f60718293a4b5c6d7e8f90',
      metric_version: 'v1.0',
      snapshot_time: '2026-11-25T08:00:00+08:00',
      schema_version: '1.0',
      sla_expires_at: '2026-11-25T10:00:00+08:00',
    },
    before_after: [
      {
        target: 'SKU-1',
        field: 'price',
        before: '109.00',
        after: '99.00',
        impact: '预计让利 10 元',
      },
    ],
    impact_scope: '影响 1 个 SKU 的前台售价',
    evidence: [{ kind: 'metric_card', ref: 'metric.price@1.0', label: '口径卡引用' }],
    rollback_plan: '恢复为 109.00',
    evidence_complete: true,
    readonly: false,
    can_approve: true,
    readonly_copy: READONLY_COPY,
    execution: null,
    result_timeline: [
      { state: 'PENDING', at: '2026-11-25T09:00:00+08:00', label: '待确认' },
    ],
    ...overrides,
  }
}

const verifiedOrder = (): ChangeOrderPayload =>
  makeChangeOrder({
    status: 'ARCHIVED',
    plan_status: 'VERIFIED',
    readonly: true,
    can_approve: false,
    readonly_copy: '该变更单已处理，如需修改请重新发起',
    execution: {
      execution_id: 'exec_m2_1',
      status: 'VERIFIED',
      before_shot: 'shot://before/wp_m2_1',
      after_shot: 'shot://after/wp_m2_1',
      verify_result: { verified: true, checked_rows: 1 },
      err_code: null,
      err_layer: null,
      ended_at: '2026-11-25T09:05:00+08:00',
    },
    result_timeline: [
      { state: 'PENDING', at: '2026-11-25T09:00:00+08:00', label: '待确认' },
      { state: 'APPROVED', at: '2026-11-25T09:01:00+08:00', label: '已批准（owner）' },
      { state: 'VERIFIED', at: '2026-11-25T09:05:00+08:00', label: '已执行并回查一致' },
    ],
  })

let wrapper: VueWrapper | null = null
let router: Router | null = null

function setRole(role: string): void {
  localStorage.clear()
  localStorage.setItem('shoppivot.token', 'test-token')
  localStorage.setItem('shoppivot.role', role)
}

async function mountPage(): Promise<VueWrapper> {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/change-orders/:id', component: P06ChangeOrder }],
  })
  await router.push(`/change-orders/${ORDER_NO}`)
  await router.isReady()
  wrapper = mount(P06ChangeOrder, {
    attachTo: document.body,
    global: { plugins: [createPinia(), router] },
  })
  await flushPromises()
  await flushPromises()
  return wrapper
}

function actionButton(action: string): HTMLButtonElement {
  const button = document.querySelector<HTMLButtonElement>(`[data-action="${action}"]`)
  expect(button).not.toBeNull()
  return button as HTMLButtonElement
}

function bodyButton(label: string): HTMLButtonElement {
  const button = Array.from(document.querySelectorAll('button')).find(
    (item) => (item.textContent ?? '').trim() === label,
  )
  expect(button).toBeTruthy()
  return button as HTMLButtonElement
}

function typeReason(value: string): void {
  const field = document.querySelector<HTMLTextAreaElement>(
    '.sp-action__control--textarea',
  )
  expect(field).not.toBeNull()
  if (!field) return
  field.value = value
  field.dispatchEvent(new Event('input'))
}

function typeApprover(value: string): void {
  const field = document.querySelector<HTMLInputElement>('[data-field="approver"]')
  expect(field).not.toBeNull()
  if (!field) return
  field.value = value
  field.dispatchEvent(new Event('input'))
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  document.body.innerHTML = ''
  api.approveWritePlan.mockResolvedValue({ plan: { status: 'VERIFIED' }, execution: null })
  api.rejectWritePlan.mockResolvedValue({ plan: { status: 'REJECTED' } })
  api.withdrawWritePlan.mockResolvedValue({ plan: { status: 'WITHDRAWN' } })
  api.compensateWritePlan.mockResolvedValue({ plan: { status: 'COMPENSATED' } })
  api.transferChangeOrder.mockResolvedValue({
    task_id: 'task-m2-1',
    status: 'PENDING',
    approver: 'backup',
    sla_expires_at: '2026-11-25T11:30:00+08:00',
  })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  router = null
  document.body.innerHTML = ''
  localStorage.clear()
})

describe('P06 · M2 L2 审批操作', () => {
  it('can_approve=true 时批准/驳回可点击，点批准先弹二次确认且不发请求', async () => {
    setRole('OWNER')
    api.fetchChangeOrder.mockResolvedValue(makeChangeOrder())

    await mountPage()

    expect(actionButton('approve').disabled).toBe(false)
    expect(actionButton('reject').disabled).toBe(false)

    actionButton('approve').click()
    await flushPromises()

    expect(api.approveWritePlan).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(zhCN.p06.actions.approveConfirmBody)
    expect(document.body.textContent).toContain(zhCN.p06.actions.approveReasonLabel)
  })

  it('确认批准后调用 approve 接口，并重新拉取变更单详情', async () => {
    setRole('OWNER')
    api.fetchChangeOrder
      .mockResolvedValueOnce(makeChangeOrder())
      .mockResolvedValueOnce(verifiedOrder())

    await mountPage()

    actionButton('approve').click()
    await flushPromises()
    typeReason('核对无误，批准执行')
    bodyButton(zhCN.p06.actions.approveConfirm).click()
    await flushPromises()
    await flushPromises()
    await flushPromises()

    expect(api.approveWritePlan).toHaveBeenCalledTimes(1)
    expect(api.approveWritePlan).toHaveBeenCalledWith('wp_m2_1', '核对无误，批准执行')
    expect(api.fetchChangeOrder).toHaveBeenCalledTimes(2)
    expect(document.body.textContent).toContain('已执行并回查一致')
    expect(document.body.textContent).toContain('shot://after/wp_m2_1')
  })

  it('execution.status=FAILED 渲染红色失败面板，含 err_code 与补偿评估提示', async () => {
    setRole('OWNER')
    api.fetchChangeOrder.mockResolvedValue(
      makeChangeOrder({
        status: 'PENDING',
        plan_status: 'FAILED',
        readonly: true,
        can_approve: false,
        readonly_copy: '该变更单已处理，如需修改请重新发起',
        execution: {
          execution_id: 'exec_failed_1',
          status: 'FAILED',
          before_shot: 'shot://before/wp_m2_1',
          after_shot: '',
          verify_result: { verified: false, reason: '参数漂移' },
          err_code: 'E009',
          err_layer: 'DATA',
          ended_at: '2026-11-25T09:06:00+08:00',
        },
        result_timeline: [
          { state: 'PENDING', at: '2026-11-25T09:00:00+08:00', label: '待确认' },
          { state: 'FAILED', at: '2026-11-25T09:06:00+08:00', label: '执行失败（已进入补偿评估）' },
        ],
      }),
    )

    await mountPage()

    const panel = document.querySelector('.sp-execution')
    expect(panel).not.toBeNull()
    expect(panel?.classList.contains('sp-execution--danger')).toBe(true)
    expect(document.querySelector('.sp-execution__banner--danger')).not.toBeNull()
    const text = document.body.textContent ?? ''
    expect(text).toContain('E009')
    expect(text).toContain('DATA')
    expect(text).toContain(zhCN.p06.execution.failedNotice)
    expect(text).toContain('参数漂移')
  })

  it('readonly=true 时操作按钮全部 disabled 并显示 readonly_copy 原文', async () => {
    setRole('VIEWER')
    const readonlyCopy = '该变更单已处理，如需修改请重新发起'
    api.fetchChangeOrder.mockResolvedValue(
      makeChangeOrder({
        status: 'PENDING',
        plan_status: 'VERIFIED',
        readonly: true,
        can_approve: false,
        readonly_copy: readonlyCopy,
        execution: verifiedOrder().execution,
      }),
    )

    await mountPage()

    for (const action of ['approve', 'reject', 'transfer', 'withdraw']) {
      expect(actionButton(action).disabled).toBe(true)
    }
    expect(document.querySelector('[data-action="compensate"]')).toBeNull()
    expect(document.body.textContent).toContain(readonlyCopy)
  })

  it('驳回理由为空时不发请求，并提示必填', async () => {
    setRole('OWNER')
    api.fetchChangeOrder.mockResolvedValue(makeChangeOrder())

    await mountPage()

    actionButton('reject').click()
    await flushPromises()
    bodyButton(zhCN.p06.actions.rejectConfirm).click()
    await flushPromises()

    expect(api.rejectWritePlan).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(zhCN.components.actionDialog.required)
  })

  it('VERIFIED 且 OWNER 可发起补偿，理由必填并调用 compensate', async () => {
    setRole('OWNER')
    api.fetchChangeOrder
      .mockResolvedValueOnce(
        makeChangeOrder({
          status: 'ARCHIVED',
          plan_status: 'VERIFIED',
          can_approve: false,
          readonly: true,
          readonly_copy: '该变更单已处理，如需修改请重新发起',
          execution: verifiedOrder().execution,
        }),
      )
      .mockResolvedValueOnce(
        makeChangeOrder({
          status: 'ARCHIVED',
          plan_status: 'COMPENSATED',
          can_approve: false,
          readonly: true,
          readonly_copy: '该变更单已处理，如需修改请重新发起',
          execution: {
            ...verifiedOrder().execution!,
            status: 'FAILED',
            err_code: 'E009',
            err_layer: 'DATA',
          },
        }),
      )

    await mountPage()

    const compensate = actionButton('compensate')
    expect(compensate.disabled).toBe(false)
    compensate.click()
    await flushPromises()
    typeReason('回查不一致，按回滚方案补偿')
    bodyButton(zhCN.p06.actions.compensateConfirm).click()
    await flushPromises()
    await flushPromises()

    expect(api.compensateWritePlan).toHaveBeenCalledWith(
      'wp_m2_1',
      '回查不一致，按回滚方案补偿',
    )
    expect(document.body.textContent).toContain(zhCN.p06.execution.compensatedNotice)
  })

  it('can_approve=true 且 PENDING 时「转交」可点击，approver 为空不发请求', async () => {
    setRole('OWNER')
    api.fetchChangeOrder.mockResolvedValue(makeChangeOrder())

    await mountPage()

    const transfer = actionButton('transfer')
    expect(transfer.disabled).toBe(false)

    transfer.click()
    await flushPromises()

    expect(api.transferChangeOrder).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(zhCN.p06.actions.transferTitle)
    expect(document.body.textContent).toContain(zhCN.p06.actions.transferApproverLabel)
    expect(document.body.textContent).toContain(zhCN.p06.actions.transferReasonLabel)

    bodyButton(zhCN.p06.actions.transferConfirm).click()
    await flushPromises()

    expect(api.transferChangeOrder).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(zhCN.p06.actions.transferApproverRequired)
  })

  it('填写 approver 后调用 transfer 接口，成功后重新拉取详情并展示新审批人与 SLA', async () => {
    setRole('OWNER')
    const newSla = '2026-11-25T11:30:00+08:00'
    const base = makeChangeOrder()
    api.fetchChangeOrder
      .mockResolvedValueOnce(makeChangeOrder())
      .mockResolvedValueOnce(
        makeChangeOrder({
          header: { ...base.header, approver: 'backup', sla_expires_at: newSla },
        }),
      )

    await mountPage()

    expect(document.body.textContent).toContain(zhCN.p06.summary.approver)
    expect(document.body.textContent).toContain('owner')

    actionButton('transfer').click()
    await flushPromises()
    typeApprover('backup')
    typeReason('临时出差，请代为审批')
    bodyButton(zhCN.p06.actions.transferConfirm).click()
    await flushPromises()
    await flushPromises()
    await flushPromises()

    expect(api.transferChangeOrder).toHaveBeenCalledTimes(1)
    expect(api.transferChangeOrder).toHaveBeenCalledWith(
      'task-m2-1',
      'backup',
      '临时出差，请代为审批',
    )
    expect(api.approveWritePlan).not.toHaveBeenCalled()
    expect(api.fetchChangeOrder).toHaveBeenCalledTimes(2)
    expect(document.body.textContent).toContain('backup')
    expect(document.body.textContent).toContain(formatDateTime(newSla))
  })
})
