# M1 只读试点验收记录（S05 / S07 / P02 / P03 / P10 / P11 / P12）

> 状态口径同 M0：**自动化已验证** = 仓库内测试可复现；**部分** = 外部条件或人工验收未完成；**待人工** = 未取得证据前不得勾通过。
> 复现：`PYTHONPATH=src:. python3 -m pytest -q`（当前 120 用例，含 M0/M1/M2），前端 `cd frontend && pnpm test && pnpm build`（当前 48 用例）。

## 范围与闸门

- 平台上限从 M0 的 L0 提升到 **L1**：允许内部工单/建议等低风险动作；`POST /api/v1/write` 仍需 L2，继续返回 403。
- S01 仍为 L0；S05 工单、S07 补货建议为 L1；不产生任何平台经营数据写入。
- n8n 只作为业务编排面，命令白名单 `job.start`，场景限 S01/S05/S07，画布不能审批 L2 或调用 `/write`。

## 验收项

| 编号 | 验收项 | 状态 | 证据 |
|---|---|---|---|
| FR-007 | S05 差评/问答工单生成与去重 | 后端 + 前端自动化已验证 | `test_s05_creates_deduped_review_ticket`；P02 页面工单表（`docs/review/frontend_verification.md`） |
| FR-008 | 工单派单、SLA 提醒与升级 | 部分：派单/关闭与 SLA 倒计时已实现；升级通知策略待接入 | `test_s05_assign_and_close_ticket`、`/todos` 的 TODO-REVIEW 倒计时 |
| FR-009 | 买家信息脱敏与证据受控访问 | 自动化已验证 | S05 工单 `content_masked`、M0 PII 扫描用例 |
| FR-010 | S07 三方可售库存对齐 | 后端 + 前端自动化已验证 | `test_s07_reconciles_three_way_inventory`；P03 三方对齐表与快照时间分列 |
| FR-011 | 断货/滞销预警与补货建议（不自动下单） | 自动化已验证 | `test_s07_suggestion_accept_via_api`；建议状态 ACCEPTED/IGNORED |
| FR-027 | P10 口径卡列表与版本 diff | 部分：列表/详情/自检已实现；当前仅单版本，diff 返回「无历史版本」 | 后端 `test_release_gate_passes_after_daily_run`；P10 页面列表/自检/抽屉 |
| FR-028 | 数据合同与漂移待办发布阻断 | 部分：DataContract 已落库；DriftEvent 待办未实现（M2） | `data_contract` 表 + `/metric-cards/{code}/release` 五项自检 |
| FR-029 | P11 机器人在线、心跳、队列积压 | 后端 + 前端自动化已验证（需先登记 Worker） | `test_worker_heartbeat_and_registration`；P11 机群卡片 |
| FR-030 | E001~E008 四层定位与重试入口 | 部分：四层分组与错误码已提供；原始日志查看器未实现 | `GET /exceptions` + `dead_letter`；`err_layer` UI/SYS/DATA/CODE |
| FR-031 | P12 角色与店铺授权配置 | 后端 + 前端自动化已验证（只读展示） | `GET /identity/roles`；P12 角色矩阵与店铺授权 |
| FR-032 | 报表订阅、通知模板与静默窗口 | 部分：订阅 CRUD + 事件/接收人合并已实现；静默窗口仅存储未参与发送判定 | `test_subscription_crud`、`test_subscription_receives_daily_report`；P12 订阅表单 |
| — | 发布自检（ADR-13 B2） | 自动化已验证 | 5 项检查：formula / mapping / policy / probe / evidence；失败 409 且不发布 |
| — | n8n 只读编排 ACL（ADR-09） | 自动化已验证 | `test_n8n_command_acl`；错误场景 400、无 token 401、命令白名单 |
| — | 组合包 `bundle_daily_ops` | 自动化已验证 | `/modules` 返回 bundle 与 depends；P09 组合包区 |

## 未完成 / 不得标记通过

1. **S05 升级通知**：工单超 SLA 的升级策略（提醒主管）尚未实现，仅有倒计时与橙态。
2. **DriftEvent / DataContract 漂移待办**：口径发布阻断只在自检内，字段漂移检测留 M2。
3. **P11 日志查看器**：当前提供异常四层定位与 Worker 心跳，原始结构化日志检索未做页面。
4. **订阅静默窗口**：字段已存储，发送侧未按静默窗口过滤；渠道仅 `CONSOLE` 实际发送，DingTalk/企微/邮件为 M2。
5. **n8n 工作流**：只交付命令 ACL 与 compose profile，未交付可导入的工作流 JSON。
6. **真实 ERP/WMS 接入**：S07 依赖后台导出文件（demo fixture 提供 `erp_inventory`/`wms_inventory`），真实系统对接留 M2/M3。
7. **浏览器级 E2E**：M1 五个页面由组件测试 + HTTP 冒烟覆盖，Playwright 浏览器证据待补。
8. 连续 2 周无 P1 故障的运行验收（M1 退出条件）需真实运行环境。

## 与文档的偏差

- S05/S07 不产生独立 Excel 报表：S05 输出工单，S07 输出差异表/建议；同源数据在 DWD/DWS，不另造一套数字。
- S07 的 ERP/WMS 数据按「受控文件交换」处理（主文档表 2-3 允许无接口时用受控文件交换）；未接真实 ERP 接口。
- P10 当前每个指标仅一个版本，版本 diff 为空；这符合 M1 只读试点范围，M2 再引入多版本与发布门禁联动。
