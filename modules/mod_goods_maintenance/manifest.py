"""mod_goods_maintenance：S02 商品链接批量维护（L2 写入动作）。

模块只提供"怎么生成变更清单、怎么写入、怎么回查/补偿"；
是否允许执行由 Kernel 闸门 + 一次性 WriteToken 决定，模块拿不到审批权。
"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
)

manifest = ModuleManifest(
    name="mod_goods_maintenance",
    version="0.5.0",
    category=ModuleCategory.BUSINESS,
    description="S02 商品价格批量维护：生成前后对比 → 人工确认 → 页面写入 → 回查",
    depends=["mod_core"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L2",
    provides=[
        Contribution(
            kind=ContributionKind.WRITE_ACTION,
            id="s02.price_update",
            config={
                "action_code": "S02.price_update",
                "scene": "S02",
                "factory": "modules.mod_goods_maintenance.handler:PriceUpdateAction",
                "description": "商品活动价批量维护（L2）",
            },
        ),
        Contribution(
            kind=ContributionKind.GATE_RULE,
            id="gate.s02.price_update",
            config={"action_code": "S02.price_update", "gate_level": "L2", "version": "1"},
        ),
        Contribution(
            kind=ContributionKind.HEALTH_CHECK,
            id="health.goods_maintenance",
            config={"factory": "modules.mod_goods_maintenance.health:probe"},
        ),
        Contribution(
            kind=ContributionKind.CQ,
            id="cq.goods_maintenance",
            config={
                "questions": [
                    "Q1 批准后修改参数是否必须重新走审批",
                    "Q2 回查不一致是否进入补偿而不是标记成功",
                ]
            },
        ),
    ],
    scenes=["S02"],
    data=[],
    config_namespace="modules.goods_maintenance",
    table_prefix="gm",
    health_checks=["health.goods_maintenance"],
    cq=["cq.goods_maintenance"],
    license="MIT",
    owner="studio",
)
