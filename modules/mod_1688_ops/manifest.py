"""mod_1688_ops：1688 选品 + 采购下单（S10 / S11）。

选品是 L0 只读；采购下单是 L2，只创建 checkout 并把支付交还给人（UTP HITL），
平台绝不代提交、代支付。
"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
)

manifest = ModuleManifest(
    name="mod_1688_ops",
    version="0.5.0",
    category=ModuleCategory.BUSINESS,
    description="1688 选品找商 + 采购下单：Skill Hub/UTP 适配，选品自动、下单人工确认",
    depends=["mod_core"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L2",
    provides=[
        Contribution(
            kind=ContributionKind.SCENE_PACKAGE,
            id="scene.s10",
            config={
                "gate_action": "S10.sourcing",
                "scene": "S10",
                "app_id": "app_demo_sourcing",
                "cron": "0 7 * * *",
                "factory": "modules.mod_1688_ops.handler:SourcingHandler",
                "default_keyword": "垃圾袋",
                "limit": 20,
                "provider": "mock",
            },
        ),
        Contribution(
            kind=ContributionKind.WRITE_ACTION,
            id="s11.purchase_order",
            config={
                "action_code": "S11.purchase_order",
                "scene": "S11",
                "factory": "modules.mod_1688_ops.handler:PurchaseOrderAction",
                "description": "1688 采购下单（L2，创建 checkout，人工支付）",
            },
        ),
        Contribution(
            kind=ContributionKind.GATE_RULE,
            id="gate.s10.sourcing",
            config={"action_code": "S10.sourcing", "gate_level": "L0", "version": "1"},
        ),
        Contribution(
            kind=ContributionKind.GATE_RULE,
            id="gate.s11.purchase_order",
            config={"action_code": "S11.purchase_order", "gate_level": "L2", "version": "1"},
        ),
        Contribution(
            kind=ContributionKind.WORKBENCH_CARD,
            id="card.sourcing",
            config={
                "card_id": "card.sourcing",
                "page_id": "P13",
                "title": "1688 选品与采购",
                "slot": "main",
                "data_endpoint": "/api/v1/sourcing/candidates",
                "empty_state_copy": "该关键词暂无候选货源",
                "order": 10,
            },
        ),
        Contribution(
            kind=ContributionKind.HEALTH_CHECK,
            id="health.1688_ops",
            config={"factory": "modules.mod_1688_ops.health:probe"},
        ),
        Contribution(
            kind=ContributionKind.CQ,
            id="cq.1688_ops",
            config={
                "questions": [
                    "Q1 品牌未授权货源是否被风险标记并阻止下单",
                    "Q2 采购单是否只创建 checkout、不代提交/代支付",
                ]
            },
        ),
    ],
    scenes=["S10", "S11"],
    data=[],
    config_namespace="modules.1688_ops",
    table_prefix="s18",
    health_checks=["health.1688_ops"],
    cq=["cq.1688_ops"],
    license="MIT",
    owner="studio",
)
