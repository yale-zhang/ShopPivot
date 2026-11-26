# M3 验收记录（第一切片：S09 结算/毛利对账 + P08）

> 状态口径同前：自动化已验证 / 部分 / 未实现。当前全量后端 133 用例，前端 67 用例。
> 复现：`PYTHONPATH=src:. python3 -m pytest -q`；前端 `cd frontend && pnpm test && pnpm build`。

## 范围

- S09 结算/账单/毛利对账：订单与结算单按订单号对齐，期望净额 = 支付金额 − 退款 − 佣金，差异 = 结算金额 − 期望净额。
- 差异分级：`MATCH / AMOUNT_DIFF / MISSING_SETTLEMENT / MISSING_ORDER`；每条保留订单与结算单双边凭据引用。
- **财务写入仍为 L3 禁止自动化**：平台只出差异与证据，不提供平账/回写入口。
- P08 对账与差异只读页：账期窗口、KPI、类型过滤、差异表与凭据、空态「无差异」。

## 验收项

| 编号 | 验收项 | 状态 | 证据 |
|---|---|---|---|
| FR-023 | P08 对账差异标注引用口径与跨库来源 | 后端 + 前端已验证 | `tests/integration/test_m3_settlement.py`；P08 页面（`frontend/tests/p08.spec.ts`） |
| S09 | 结算/毛利对账 | **部分**：演示导出文件对账完成；真实结算接口/账期规则待接 | `modules/mod_settlement_recon/handler.py`；`SettlementReconciler` 单测经集成覆盖 |
| — | 差异逐条可追溯双边凭据 | 自动化已验证 | 每条差异含 `order_ref` / `settlement_ref`；D0-1002 金额差异 -17.00 |
| — | 缺结算/缺订单分类 | 自动化已验证 | `MISSING_SETTLEMENT` / `MISSING_ORDER` 各 1 条 |
| — | 财务写入禁止 | 自动化已验证 | 无任何 `/write` 或回写端点；P08 无确认/平账按钮 |
| — | 空态不冒充 0 | 自动化已验证 | `test_s09_empty_state_before_any_run`：`empty_copy=无差异` |
| — | 迁移 | 自动化已验证 | `migrations/versions/0006_settlement.py` |
| S10 | 1688 选品（关键词/评分/风险） | mock 已验证；真实 Skill CLI 待 AK UAT | `modules/mod_1688_ops/handler.py`、`test_m3_1688.py` |
| S11 | 1688 采购下单（L2，checkout，人工支付） | mock 已验证；真实 UTP 待 UAT | `S11.purchase_order`、`PurchaseOrderAction` |
| P13 | 选品与采购页 | 后端 + 前端已验证 | `/sourcing/search`、`/purchases`；`frontend/tests/p13.spec.ts` |
| — | 品牌未授权/起订量阻断 | 自动化已验证 | `test_purchase_plan_rejects_brand_and_moq` |
| — | 不代付边界 | 自动化已验证 | 采购单 `AWAITING_PAYMENT`；无支付完成调用 |
| — | 迁移 | 自动化已验证 | `migrations/versions/0007_1688_ops.py` |
| S0/S1 | Skill 运行时：目录/信任/执行/运行记录 | 已验证（mock/CLI 未真实 UAT） | `kernel/contexts/skill/`、`tests/integration/test_skill_runtime.py` |
| P14 | 技能中心只读页 | 已验证 | `frontend/tests/p14.spec.ts`、`/skills/catalog` |
| — | skill_run 迁移 | 自动化已验证 | `migrations/versions/0008_skill_runtime.py` |
| S2a | Skill 安装/校验/启停/绑定 | 后端 + 前端已验证 | `skill_lifecycle.py`、`test_skill_runtime.py`、`frontend/tests/p14.spec.ts`、迁移 0009 |
| S2b-1 | 安装包安全解压/校验 | 后端 + 前端已验证（本地受控 zip；在线下载/签名待做） | `package.py`、`frontend/tests/p14.spec.ts` |
| S2b-1 | S11 采购迁移 Skill Runtime | 后端已验证（mock/CLI；真实 UTP 待 UAT） | `purchase.checkout/status/cancel`、`test_m3_1688.py` skill_run 断言 |

## 未完成（M3 后续）

1. S06 竞品行情监测（只读、合规评估）。
2. S12 1688 铺货（`distribute_offer`）与真实 AK/UTP UAT。
3. S08 大促作战看板、`bundle_promo`、大促日历与降级策略。
4. 语义层（薄本体 12 概念、SemanticGap、探针/CQ 发布门禁）——ADR-13 仍为有条件生效。
4. 真实拼多多/京东结算接口、账期与退款口径对齐；当前用演示导出文件。
6. 浏览器级 E2E 与连续运行验收。

## 与文档的偏差

- S09 以订单级差异为主（演示数据粒度），月度/账期汇总由 P08 窗口展示；真实账期规则接入后再补按账期聚合。
- 财务确认状态字段保留 `OPEN`，未提供财务“认定/签字”流程（属人工线下 + 审计，平台不做财务写入）。
