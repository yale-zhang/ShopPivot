# M2 写入闸门验收记录（L2：WritePlan → 审批 → Token → 执行 → 回查 → 归档/补偿）

> 状态口径同前：**自动化已验证** = 仓库内测试可复现；**部分** = 真实平台/外部条件未满足；**未实现** = 本阶段明确不做。
> 复现：`PYTHONPATH=src:. python3 -m pytest -q`（当前 118 用例），前端 `cd frontend && pnpm test && pnpm build`（当前 44 用例）。

## 闸门链路

1. `POST /api/v1/write-plans`：校验动作必须为 L2 且平台上限 ≥ L2；动作处理器生成冻结的前后值、影响范围、回滚方案、证据引用。
2. 计划落库 `write_plan` + 创建 `ApprovalTask`（P05 待办、P06 详情）。
3. `POST /write-plans/{id}/approve`：审批人确认（前端二次确认 + 理由）→ 服务端生成变更单号与变更前截图证据 → 批准 → 签发一次性 WriteToken（**只存 sha256，绑定 task_id/plan_id，TTL 300s，单次消费**）。
4. 同请求内执行动作 → 回查平台状态 → 一致才归档（补齐执行后截图、任务 ARCHIVED、计划 VERIFIED）。
5. 失败：参数漂移/回查不一致 → 计划 FAILED；若已写入则自动补偿并置 COMPENSATED，不假装成功。

## 验收项

| 编号 | 验收项 | 状态 | 证据 |
|---|---|---|---|
| FR-018 | P06 前后对比与影响范围 | 后端 + 前端已验证 | `write_plan.rows` / `impact_scope`；P06 页面与 `frontend/tests/m2.spec.ts` |
| FR-019 | 证据包与回滚方案强制校验 | 自动化已验证 | 无回滚方案不允许建计划（`WritePlan.create`）；批准要求操作人/时间/变更单/变更前截图 |
| FR-020 | 批准 / 驳回 / 转交 / 撤回与二次确认 | 后端 + 前端已验证 | `test_transfer_resets_approver_and_sla`；P06 转交弹窗（`frontend/tests/m2.spec.ts`） |
| FR-021 | 一次性 WriteToken 与执行后回查 | 自动化已验证 | token 单次消费/绑定校验：`test_write_token_is_single_use_and_bound`；回查/归档：`test_l2_write_plan_approve_execute_verify_archive` |
| S02 | 商品价格批量维护（L2） | **部分**：本地受控状态模拟页面写入，真实平台页面写入待桌面执行面 | `modules/mod_goods_maintenance/handler.py`、`test_price_drift_after_plan_blocks_execution` |
| FR-012 | S03 活动提报与台账 | **部分**：重复提报/活动价高于日常价校验 + L2 审批/执行/回查已实现；资格/库存/活动互斥与真实报名页未接 | `test_s03_campaign_apply_full_chain_and_duplicate_block`、`test_s03_rejects_activity_price_above_daily_price` |
| FR-013 | S04 投放归集与投产比预警 | 后端 + 前端已验证：按计划汇总、阈值预警、只出建议 | `test_s04_ads_monitor_and_alert_summary`、`/ads/summary`、P04 页面（`frontend/tests/p04.spec.ts`） |
| FR-022 | P07 审批记录与审计检索 | 后端 + 前端已验证 | `GET /approvals/history`、`GET /audit?action=&actor=&object_id=&from=&to=`；`test_audit_filters_and_approval_history` |
| — | 审批转交并重置 SLA | 后端已验证 | `test_transfer_resets_approver_and_sla`；`approval_task.approver` + 迁移 0005 |
| — | SLA 提醒 / 升级 / 超时作废 | 自动化已验证 | `EscalateApprovalsUseCase`；`test_escalation_reminds_escalates_and_expires_once`；Celery 每 5 分钟 |
| — | 变更单发起 | 后端 + 前端已验证 | `POST /write-plans`、`GET /platform/price-list`；P05 新建变更单（M2 前端） |
| — | 审计筛选 | 自动化已验证 | `/audit` 支持 action/actor/object_type/object_id/from/to |
| — | 参数漂移阻断执行 | 自动化已验证 | 审批后外部改价 → `E006`、计划 FAILED、不覆盖外部状态 |
| — | 回查不一致自动补偿 | 自动化已验证 | `test_verification_failure_compensates`；状态 COMPENSATED |
| — | `/write` 对外不可直调 | 自动化已验证 | `tests/e2e/test_s01_e2e.py::test_worker_api_write_is_disabled_and_query_works` |
| — | M1 平台上限无法创建 L2 计划 | 自动化已验证 | `test_m1_ceiling_denies_l2_plan` |
| — | VIEWER 不能批准 | 自动化已验证 | `test_l2_viewer_cannot_approve` |
| — | 写入表迁移 | 自动化已验证 | `migrations/versions/0004_write_gate.py` + 迁移 up/down 测试 |

## 安全边界

- 默认平台上限 **L2**（M0=L0 / M1=L1 / M2=L2）；但**不会自动产生任何写入**：必须显式建计划并经人工批准。
- 业务端/画布不能直调 `/write`；token 明文不落库，单次有效，过期或跨 task/plan 均拒绝。
- 审批四要素（操作人/确认时间/变更单号/变更前截图）在批准时校验；执行后截图在回查通过后补入，归档时四要素 + 后截图齐全。
- 审批后参数变化（外部改价）→ 停止执行，不覆盖现场、不自动补偿。
- 只有真正写入过才触发补偿；未写入的失败保留外部现场。

## 未完成 / 不得标记通过

1. **真实平台页面写入**：当前用 `storage/platform_state/demo_prices.json` 模拟；接拼多多商家后台需桌面执行面与元素稳定性组件。
2. **真实 S03 活动页面提交、S04 调价/调预算执行、财务回写**：未实现（S03 已用本地状态模拟，S04 只出建议）。
3. **转交**：后端无转交端点，P06「转交」保持 disabled。
4. **Worker HTTP `/write` 契约调用**：M2 切片在控制面进程内执行；Token 校验与状态机已独立，拆 Worker 时不改契约。
5. **撤回**：同步执行下"已批准未执行"窗口很短，撤回接口已实现但主要供测试/未来异步队列。
6. 浏览器级 E2E 与真实连续运行验收（M2 退出条件）未执行；已做 P06 组件测试 + HTTP 冒烟。
7. **变更单发起入口**：P05 提供新建表单（S02/S03），底层仍是 `POST /write-plans`；真实商品/活动清单需接平台接口（当前价格清单来自本地演示状态）。
9. **S03 校验范围**：已做重复提报与价格上限；平台资格、库存、活动互斥校验需活动接口/页面接入后补齐。
10. **S04 不执行调价/调预算**：只出预警与建议；调价动作应走 S02/S03 类 L2 计划，不在此模块内自动执行。
11. **审批升级通知渠道**：提醒/升级写入通知表与审计，实际渠道仍为 CONSOLE；钉钉/企微/邮件留 M3。
8. **转交**：后端与前端均未实现，按钮 disabled。

## 与文档的细化

- 批准阶段要求"操作人/确认时间/变更单号/变更前截图"，执行后回查通过再补"执行后截图"；归档仍要求四要素完整。这比代码骨架「批准即要求前后截图」更符合实际操作时序，且未降低归档标准。
- WritePlan 使用独立 `RunId` 作为关联键，不与 `run_instance` 强绑定（变更单不是一次采集运行）。
