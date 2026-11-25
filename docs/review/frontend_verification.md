# 前端 M0 验证记录

## 环境与命令

```bash
cd frontend
npm_config_cache=/tmp/npm-cache pnpm install --store-dir /tmp/pnpm-store
pnpm build   # vue-tsc --noEmit && vite build
pnpm test    # vitest run
```

## 结果（2026-11-25）

| 检查 | 结果 |
|---|---|
| `pnpm build` | 通过：1713 modules transformed，`dist/index.html` + JS 457.54 kB + CSS 423.58 kB |
| `pnpm test` | 通过：2 个 spec / 13 tests（copy.spec.ts 7、states.spec.ts 6） |
| 开发服务器 + 代理 | `http://127.0.0.1:5173/` 200；`/api/v1/healthz` 经 Vite 代理返回 200 |
| 登录链路 | 经代理 `POST /api/v1/auth/login` 返回 access_token，角色 OWNER |
| 实时数据 | `GET /api/v1/reports/latest` 返回 12 列 / 1 行 / 1 条告警（cvr 0.50 < 0.6） |

## 已覆盖的验收点

- F-02：12 列渲染；比率列 `不可加（比率类）`；`不适用`/`—` 非 0。
- F-04：P05 超时待办橙态与 `已超时自动作废，需重新发起变更单`；P06 四按钮 disabled + `需审批后执行（当前只读模式）`。
- F-05：P09 模块列表、状态徽标、阻断文案 `模块 <name> 未加载：<reason>`、禁用按钮（OWNER）。
- F-06：空态原文、错误态（err_code + 四层）、只读态；测试断言空态不含 `0`/`0.00`。
- 三步下钻：指标 → 口径卡抽屉 → run_id → 运行详情 → ODS 证据（默认 masked，显示脱敏提示）。
- 导出：blob 下载 xlsx，按钮附近展示 watermark 摘要。

## 未执行

- **真实浏览器级 E2E（Playwright）未执行**：M0 未安装浏览器二进制。当前用「组件测试 + HTTP 冒烟 + 设计方 mock 视觉冒烟」替代；F-01/F-05 的浏览器级证据留待 M1 补 Playwright。
- 时间窗/口径版本下拉目前只触发重新请求与展示更新，后端 M0 仅按平台/店铺取最新报表（口径版本随报表返回），不做历史窗口查询。
- P06 审批四按钮在 M0 全禁用；后端 `/write` 返回 403，批准链路 M2 交付。

## 偏差说明

1. 引入了 Element Plus 全量样式表（组件只用 ElSelect/ElButton/ElTable/ElTag），以便统一覆盖下拉与表格样式。
2. P09 禁用模块属于控制面操作，只读（L0）不限制模块装卸；后端同样允许 OWNER 禁用、重新启用需重启。
3. 运行节点完全取自 `/runs/{run_id}`，不伪造 T0~T6。

---

# M1 前端验证追加（2026-11-25）

## 新增页面

| 页面 | 路由 | 主要验证点 |
|---|---|---|
| P02 评价与口碑 | `/p02` | KPI（待处理/已派单/超时/已关闭）、DSR 趋势、工单表、脱敏内容、SLA 倒计时、派单/关闭（OWNER/EDITOR）；VIEWER 隐藏操作 |
| P03 库存与补货 | `/p03` | 三方对齐表、差异类型、三方快照时间分列、补货建议采纳/忽略、`snapshot_note`、空态「三方库存一致，无差异」 |
| P10 口径与数据合同 | `/p10` | 口径卡列表、最近自检徽标、五项发布自检（成功/409 失败逐项）、详情抽屉、版本 diff |
| P11 机器人与日志 | `/p11` | Worker 心跳/能力/队列、登记本机 Worker、异常四层 UI/SYS/DATA/CODE 分组、run_id 运行详情 |
| P12 权限与订阅 | `/p12` | 角色矩阵、店铺授权、订阅 CRUD、通知模板、只读角色隐藏管理动作 |

## 验证结果

```text
cd frontend
pnpm test
  tests/errors.spec.ts   2 passed
  tests/copy.spec.ts     7 passed
  tests/states.spec.ts   6 passed
  tests/m1.spec.ts      11 passed
  Test Files 4 passed / Tests 26 passed

pnpm build
  vue-tsc --noEmit 0 error；1737 modules transformed；built in ~4s
  （仅 Vite chunk >500kB 体积提示，非错误）
```

HTTP 冒烟（API 8010 / 前端 5180 临时端口，完成后已关闭）：
- `/p02` `/p03` `/p10` `/p11` `/p12` 均返回 200；
- 经 Vite 代理访问 `/api/v1/healthz` 200；
- `/reviews/summary`、`/reviews/tickets`、`/inventory/reconciliation`、`/metric-cards`、`/workers`、`/subscriptions`、`/identity/roles`、`/notifications/templates` 均 200 且字段与页面类型一致。

## M1 前端偏差

1. P10 的发布自检结果以内联面板呈现（5 项检查常驻可见），详情与版本对比仍在右侧抽屉。
2. P11 的 run_id 直接打开既有运行详情抽屉，不跳 P01。
3. P02/P03 未做状态筛选 Tab，按接口默认返回展示；KPI 计数取 summary/counts。
4. 未引入图表库：P02 DSR 趋势为纯 CSS 柱状条。
5. P12 阈值 JSON 只接受数值；静默窗口仅保存，发送侧尚未按窗口过滤（与 M1 后端一致）。

## 仍未执行

- 真实浏览器 Playwright 验收（未安装浏览器二进制）；当前为组件测试 + 路由/API HTTP 冒烟。
- 与真实拼多多/ERP/WMS 数据联调（当前 demo fixture）。

---

# M2 前端验证追加（P06 L2 审批动作）

## 变更
- P06 接入 `can_approve` / `plan_status` / `execution` / `result_timeline`；
- 批准（二次确认 + 可选理由）、驳回（理由必填）、撤回（APPROVED 未执行）、补偿（VERIFIED，OWNER）四类操作；
- 新增执行结果面板：VERIFIED 绿 / FAILED 红 / RUNNING 橙，展示前后截图引用、`verify_result`、`err_code/err_layer`、结束时间与补偿状态；
- 「转交」按钮保留但恒 disabled，title「转交在后续版本交付」；
- 失败优先展示后端 `message`，Toast + 弹窗错误区双通道。

## 验证结果

```text
cd frontend
pnpm build   # vue-tsc --noEmit 0 error；vite build 成功（仅 chunk 体积提示）
pnpm test
  tests/errors.spec.ts   2 passed
  tests/copy.spec.ts     7 passed
  tests/states.spec.ts   6 passed
  tests/m1.spec.ts      11 passed
  tests/m2.spec.ts       6 passed
  Test Files 5 passed / Tests 32 passed
```

HTTP 冒烟（临时 API 8020 + Vite 5190，完成后关闭）：
- 创建计划 → P06 `PENDING_APPROVAL`（`can_approve=true`，1 行前后对比）；
- 批准 → 计划 VERIFIED、执行 VERIFIED；
- 再查 P06 → 任务 ARCHIVED、`readonly=true`、执行 VERIFIED；
- `/change-orders/{id}` 前端路由 200；`/api/v1/healthz` 经代理 200。

## M2 前端偏差

1. 转交未实现，按钮禁用。
2. 后端批准同步执行，`plan_status=APPROVED` 窗口很短；撤回入口按契约实现但实际少见。
3. 补偿入口仅 OWNER 且 `plan_status=VERIFIED` 时显示，后端仍二次校验 `approve_l2`。
4. 未做浏览器级 Playwright；当前为 6 条 M2 组件测试 + HTTP 冒烟。

---

# M2 前端追加（P04 投放页 + P06 转交）

## 新增/变更
- 新增 P04 `/p04`：总花费/总成交/整体投产比/预警数 KPI；计划表（花费、成交、投产比、预警等级、建议）；纯 CSS 花费/成交条形；`note` 常驻；空态用 `empty_copy`；ROI 为空显示「不适用」。
- P06 启用「转交」：仅在 `can_approve=true && status=PENDING` 时可点，弹窗填写新审批人与理由，成功后刷新详情与 SLA；单头新增「当前审批人」。
- 预警等级中文：ALERT=高风险、WATCH=关注、OK=达标。

## 验证结果

```text
cd frontend
pnpm build   # vue-tsc + vite build 通过
pnpm test
  tests/errors.spec.ts   2
  tests/copy.spec.ts     7
  tests/states.spec.ts   6
  tests/p04.spec.ts      3
  tests/m2.spec.ts       8
  tests/m1.spec.ts      11
  Test Files 6 passed / Tests 37 passed
```

HTTP 冒烟（临时 API 8030 + Vite 5200，已完成关闭）：
- `/ads/summary`：2 个计划，`{OK:1, ALERT:1}`，总花费 400、总成交 1250、整体 ROI 3.12；
- 创建 S03 活动提报计划并转交 `editor`：P06 `header.approver=editor`、`can_approve=true`；
- `/p04`、`/change-orders/{task_id}` 路由 200，`/src/pages/P04Ads.vue` 200，代理 `/api/v1/healthz` 200。

## 偏差
- 转交以填单弹窗作为确认步骤，未再叠加二次确认框。
- P04 `note` 原文包含「不自动调价 / 不自动调预算」的否定表述，页面无任何调价入口。

---

# M2 前端追加（P07 审批审计 + 新建变更单）

## 新增/变更
- P07 `/p07`：状态/动作/审批人筛选；历史表（创建时间、变更单号、动作、审批人、状态、执行状态、行数、SLA）；行点击抽屉展示概要、审计时间线、前后对比/证据/执行结果，并可打开 P06；含 loading/403/空态。
- P05「新建变更单」：OWNER/EDITOR 可见；S02 价格维护从 `/platform/price-list` 选 SKU 并填目标价，S03 活动提报填活动 ID/SKU/活动价；支持多行、防抖、前端校验，成功后跳转 P06。
- 新增 `ChangeOrderCreateDialog.vue`、`P07Audit.vue`、`tests/p07.spec.ts`（7 条）。

## 验证结果

```text
cd frontend
pnpm build   # vue-tsc + vite build 通过
pnpm test
  tests/errors.spec.ts   2
  tests/copy.spec.ts     7
  tests/states.spec.ts   6
  tests/p04.spec.ts      3
  tests/m2.spec.ts       8
  tests/p07.spec.ts      7
  tests/m1.spec.ts      11
  Test Files 7 passed / Tests 44 passed
```

HTTP 冒烟（临时 API 8040 + Vite 5210，已完成关闭）：
- `/approvals/history` 200（含已归档计划、执行状态）；
- `/audit` 200；`/platform/price-list` 200（5 个 SKU）；
- `/p07`、`/p05`、`/p04` 路由 200，代理 `/api/v1/healthz` 200。

## 偏差
- 创建 S03 计划时前端显式传 `scene:"S03"`，避免后端默认 S02。
- P07 带「重置」筛选与可聚焦的变更单号按钮（可访问性增强）。
- 仍未做浏览器级 Playwright；当前为 44 条组件测试 + HTTP 冒烟。
