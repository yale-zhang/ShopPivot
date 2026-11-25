# 店枢 ShopPivot · ADR 索引（镜像主文档表 12-3）

> 主文档为唯一权威来源；本文件只登记**代码实现落点**，状态与主文档一致。

| 编号 | 决策摘要 | 状态 | 代码落点 |
|---|---|---|---|
| ADR-01 | 自建平台控制面 + RPA 作执行引擎 | 生效 | `src/bootstrap/container.py`、`src/kernel/runtime/` |
| ADR-02 | 执行栈锁定开源组合 + 自建 Worker API，不引入影刀 | 生效（已锁定） | `src/worker/`、`kernel/contracts/worker_api.py`；M0 无桌面执行 |
| ADR-03 | 混合部署为目标形态，桌面执行面按需启用 | 已修正 | `deploy/docker-compose.yml` 仅控制面；`docs/runbooks/desktop_pool.md` |
| ADR-04 | 三级取数：官方接口 ＞ 后台导出 ＞ 网页兜底 | 生效 | `kernel/contexts/integration/domain/fetch_strategy.py`（M0 前两级） |
| ADR-05 | 统一数据模型 + 字段适配层 | 生效 | `kernel/contexts/metric_data/domain/canonical_record.py`、`modules/mod_platform_*/adapter.py` |
| ADR-06 | AI 不直接驱动生产执行 | 生效 | 无 AI 执行入口；扫描见 `tests/security/` |
| ADR-07 | PostgreSQL + Redis + 对象存储，试点不上数仓 | 生效 | `kernel/persistence/base.py`、`deploy/docker-compose.yml` |
| ADR-08 | 写入分级 L0~L3 + 人工确认闸门 | 生效（M2：计划/审批/一次性 token/执行/回查） | `shared/gate_level.py`、`kernel/contexts/approval/domain/`、`approval/application/write_flow.py` |
| ADR-09 | 引入 n8n 作业务编排面（M1 起） | 生效（M1：命令 ACL + compose profile） | `src/bootstrap/routers/n8n_router.py`、`n8n/credentials.policy.md`、`deploy/docker-compose.yml`（profile n8n） |
| ADR-10 | Worker API 契约先于资源建设 | 生效 | `docs/contracts/worker_api.schema.json`、`tests/contract/` |
| ADR-11 | DDD 限界上下文 + 四层依赖倒置 | 生效 | `src/kernel/contexts/*/{domain,application,infrastructure,interfaces}` |
| ADR-12 | 先交付 M0 最小原型，写入与桌面池延后 | 生效 | 本仓库 M0 范围；`docs/review/m0_acceptance.md` |
| ADR-13 | 薄本体 + 口径卡 + 发布自检（M1 起） | 有条件生效（B1/B2 已落地，薄本体未建） | `metric_data/application/release_gate.py`、`metric_card` 契约；本体未建 |
| ADR-14 | 模块化单体 + 显式扩展点 | 生效 | `kernel/module_loader.py`、`kernel/registry.py`、`modules/` |
| ADR-15 | 自用前提下许可风险降为内部台账 + 三触发器 | 生效 | `docs/licenses.csv`、主文档 11.4 |
| ADR-16 | manifest 声明 gate_level_max / requires / api_compat，双重强校验 | 生效 | `kernel/contracts/manifest_schema.py`、`kernel/module_loader.py` |

## M0 实现中新增的工程约定（不新增 ADR）

1. **运行时启停不做热装载**：启动期一次装配，禁用通过持久化 `module_state` + 查询期过滤贡献实现；"禁用后无残留"以可观测行为验证（P09/卡片/调度）。M1 再评估热装载。
2. **M0 执行在控制面进程内完成**：无桌面、无独立队列；`src/worker` 只做能力登记与心跳。Worker API 契约已固定，M2 拆分执行进程不改契约。
3. **E001~E008 / LOG-01~05 为临时注册表**：定义在外部《RPA 应用项目方案（模板）》，模板齐备后只改 `shared/errors/registry.py`。
4. **演示 L2 待办为测试替身**：仅 `SHOPPIVOT_ALLOW_L2_SIMULATION=true` 时可由 CLI 构造，用于 F-04 验收；不签发 WriteToken、不调用 `/write`。
5. **M1 平台上限 L1 / M2 平台上限 L2**：S05 工单/S07 建议属内部记录；S02 价格维护为 L2，必须走 WritePlan 审批；`/write` 对外仍 403。M0/M1 验收测试显式使用 L0/L1 保持原口径。
6. **M2 写入执行在控制面进程内完成**：单机模拟页面写入（`storage/platform_state`），Worker `/write` 契约与桌面池留到真正接入平台页面时启用。
