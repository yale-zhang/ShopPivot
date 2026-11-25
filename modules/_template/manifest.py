"""新模块脚手架（复制到 modules/mod_xxx 后按下表改名）。

复制清单：
1. 目录改名 `mod_<domain>`，manifest.name 同步；
2. depends 只写直接依赖；
3. gate_level_max 默认 L0，需要写入必须走变更单 + 平台上限调整；
4. provides 每项带稳定 ID；
5. data[] 按 permissions → metric_cards → workbench → seed 顺序登记；
6. 写 migrations/<version>/ 与幂等 hooks；
7. 写契约测试 + CQ 自检；
8. 干净库安装 → 升级 → 禁用 → 重新启用，确认无残留。
"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
)

manifest = ModuleManifest(
    name="mod_template",
    version="0.1.0",
    category=ModuleCategory.BUSINESS,
    description="TODO: 一句话说明这个模块提供什么能力",
    depends=["mod_core"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L0",
    provides=[
        Contribution(
            kind=ContributionKind.WORKBENCH_CARD,
            id="card.template",
            config={
                "card_id": "card.template",
                "page_id": "P09",
                "title": "模板卡片",
                "data_endpoint": "/api/v1/modules",
                "empty_state_copy": "暂无可展示内容",
                "order": 999,
            },
        )
    ],
    scenes=[],
    data=["security/permissions.csv", "data/metric_cards/example.yaml"],
    config_namespace="modules.template",
    table_prefix="tpl",
    license="MIT",
    owner="studio",
)
