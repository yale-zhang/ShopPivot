# M0 验收记录（主文档表 7-5 / 表 9-23 / 表 3-31）

> 状态口径：**自动化已验证** = 仓库内测试可复现；**部分** = 代码与自动化已覆盖但外部条件未满足；**待人工** = 必须连续运行或人工核对，未取得证据前不得勾「通过」。
> 复现命令：`PYTHONPATH=src:. python3 -m pytest -q`（当前全量 118 用例，含 M1/M2）与 `make demo`。

## 表 7-5 M0 八项

| 序号 | 验收项 | 状态 | 证据 |
|---|---|---|---|
| 01 | 连续运行 2 周，日报与人工核对一致率 100% | **部分**：单次一致性有自动化断言，2 周连续运行与人工核对待执行 | `tests/e2e/test_s01_e2e.py::test_s01_full_chain_and_three_step_drilldown`；人工核对表待补 |
| 02 | 采集成功率区分「平台无数据」与「抓取失败」 | 自动化已验证 | 空窗口 → `data_state=EMPTY`；无导出文件 → `E004` + 死信；`tests/e2e/test_m0_states.py::test_f02...`、`tests/integration/test_repositories.py::test_failure_goes_to_dead_letter_and_alerts` |
| 03 | 任一结果可用 run_id 反查原始报文、口径版本、日志与报表文件 | 自动化已验证 | 三步下钻 e2e：指标 → `/metric-cards/{code}` → `/runs/{run_id}` → `/evidence/{id}` |
| 04 | 指标改一处配置即可生效，日报/看板同源，无硬编码公式 | 自动化已验证 | 12 张口径卡在 `modules/mod_daily_report/data/metric_cards/`；`MetricCalculator` 单测；报表与 API 同源 DWS |
| 05 | E001~E008 可按四层检索，失败进死信并告警 | 自动化已验证 | `exception_record` + `dead_letter` + `EVT-07`；`tests/integration/test_repositories.py::test_failure_goes_to_dead_letter_and_alerts` |
| 06 | 含个人信息字段在日志与报表中 100% 脱敏 | 自动化已验证 | `tests/security/test_pii_and_audit.py::test_pii_never_reaches_report_logs_or_notifications` |
| 07 | Worker API 契约已定稿并有契约测试 | 自动化已验证 | `docs/contracts/worker_api.schema.json` + `tests/contract/test_worker_api_contract.py` |
| 08 | 未部署桌面池、未调用 `/write`，安全评审通过 | 自动化已验证（安全评审待签字） | `deploy/docker-compose.yml` 无 desktop 服务；`/write` 403 测试 |

## 表 9-23 M0 新增三条

| 编号 | 验收项 | 状态 | 证据 |
|---|---|---|---|
| A | 装第二个模块（`mod_probe_card`）不改 Kernel 代码 | 自动化已验证 | `tests/modules/test_acceptance.py::test_acceptance_a_second_module_without_kernel_change` |
| B | 循环依赖 / api_compat 不匹配 / data 漏登记 三种情况启动阻断并给模块名 | 自动化已验证 | 同文件 B 组三个用例；issue 文案含模块名 |
| C | 声明 `gate_level_max=L2` 在平台上限 L0 下被拒；禁用 `mod_daily_report` 后无残留 | 自动化已验证 | 同文件 C 组两个用例；`/modules/{name}/disable` e2e 复核 |

## 表 3-31 M0 功能验收增补

| 编号 | 验收项 | 状态 | 证据 |
|---|---|---|---|
| F-01 | 四上下文生效，P01 卡片同源刷新 | 后端 + 前端组件已验证；浏览器级待补 | `docs/review/frontend_verification.md`；P01 监听 context store 重新请求 |
| F-02 | 日报 12 列全渲染；分母为零「不适用」、比率标「不可加」 | 自动化已验证 | `test_f02_zero_denominator_and_non_additive`、导出表头断言 |
| F-03 | 三步下钻链路通 | 自动化已验证 | `test_s01_full_chain_and_three_step_drilldown` |
| F-04 | 超时 L2 待办自动作废而非默认执行 | 自动化已验证 | `test_f04_overdue_l2_is_expired_not_executed`；`POST /write` 仍 403 |
| F-05 | 装/禁模块后卡片自动挂载/摘除且无残留 | 后端自动化已验证；前端组件已验证 | `test_f05_disable_module_removes_cards_without_residue`、模块验收 A、P09 组件测试 |
| F-06 | 空态/取数失败/只读三态与表 3-28 一致 | 后端 + 前端自动化已验证 | `test_f06_readonly_and_error_states`、`frontend/tests/states.spec.ts` |

## 未完成 / 不得标记通过

1. 连续 2 周运行与日报人工核对（需真实运行环境与运营签字）。
2. 平台接口权限、账号风控、脱敏范围的 IT/安全评审签字。
3. 前端浏览器级 Playwright 验收（构建/组件/HTTP 冒烟已过，浏览器二进制未装）。
4. 真实拼多多店铺授权（当前 M0 用 `mod_platform_demo` 确定性 fixture 验证链路；切 pdd 不改主链）。

## 已知简化（不改变验收口径）

- M0 执行在控制面进程内完成，无独立执行队列；Worker 进程只做心跳与能力登记。
- 演示 L2 待办仅用于 F-04，由 CLI 显式构造；不签发 WriteToken、不执行写入。
- `E001~E008` / `LOG-01~05` 为临时注册表（外部模板未随文档提供）。
