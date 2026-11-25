# 模块化底座复核清单（主文档表 9-26）

> 规则：未取得证据前不得把「□ 完成」改为「✓」。证据路径均可在仓库内复现。

| 序 | 复核项 | 判定 | 证据 |
|---|---|---|---|
| 01 | 「自用、不对外、不分发」前提已写入文档控制信息，并列出三个触发器 | ✓ 完成 | 主文档表 0-0；`README.md`「安全与合规」；`docs/licenses.csv` note 列；本文件下方「三触发器」 |
| 02 | 不使用 Camunda 8 / Odoo 运行时；Odoo 仅作机制参考 | ✓ 完成 | 依赖清单 `pyproject.toml` 无 camunda / odoo；`kernel/module_loader.py` 自研；`docs/adr_index.md` |
| 03 | 7 个限界上下文与模块分类不是一一对应，Kernel 不被模块改写 | ✓ 完成 | `src/kernel/contexts/*`（7 个）；`modules/` 5 个模块；`tests/unit/test_domain_purity.py`；`tests/modules/test_acceptance.py::test_acceptance_a...` |
| 04 | manifest Schema、扩展点 Protocol、api_compat 版本策略评审通过 | ✓ 完成（评审记录待签） | `docs/contracts/module_manifest.schema.json`、`src/kernel/contracts/extension_points.py`、`tests/contract/test_manifest_schema.py` |
| 05 | M0 新增三条验收（A/B/C）与「不做本体能力」边界对齐 | ✓ 完成 | `tests/modules/test_acceptance.py`；`docs/review/m0_acceptance.md`；无 SemanticConcept 实现 |
| 06 | licenses.csv 建立，含 n8n / AGPL / ELv2 / BSL / MPL 组件与是否修改标记 | ✓ 完成 | `docs/licenses.csv`；`scripts/check_docs.py` 校验无 UNKNOWN |
| 07 | 表标题唯一性与章节互引用检查 | **待文档维护人** | 主文档为权威来源；代码侧只校验契约/许可/验收文档存在（`scripts/check_docs.py`） |

## 三触发器（任一出现即恢复完整许可复核）

1. 代码公开 / 开源发布；
2. 镜像或部署包交付外部；
3. 转为代运营、对外服务或商业产品。

执行动作固定：暂停外发 → 跑 SBOM / 修改文件清单 / NOTICE → 法务意见 → 更新 `licenses.csv` 与主文档表 0-0；责任人＝工作室 Owner。

## 模块组合测试策略（表 9-25 风险控制）

- 只测「核心组合 + 每模块单独 + 依赖边界」：M0 核心组合 = `mod_core + mod_worker_headless + mod_platform_demo + mod_daily_report`。
- 循环依赖、api_compat 不匹配、data 漏登记、越权 gate_level 四类阻断均有自动化用例。
- 禁用后残留检查：`/workbench/nav`、`/workbench/cards`、`ScenePackage`、`MetricCard` 四处均断言为空。
- 未做：运行时热装载（M0 明确不做，README 已标注）。
