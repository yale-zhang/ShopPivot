"""mod_settlement_recon：S09 结算/账单/毛利对账（只读，财务人工认定）。"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    CapabilityRequirement,
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
)

manifest = ModuleManifest(
    name="mod_settlement_recon",
    version="0.5.0",
    category=ModuleCategory.BUSINESS,
    description="S09 结算对账：订单与结算单按主键对齐 → 差异分级 → 双边凭据",
    depends=["mod_core", "mod_worker_headless"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L0",
    requires=[CapabilityRequirement(name="EXPORT_PARSE")],
    provides=[
        Contribution(
            kind=ContributionKind.SCENE_PACKAGE,
            id="scene.s09",
            config={
                "gate_action": "S09.report",
                "scene": "S09",
                "app_id": "app_demo_settlement",
                "cron": "0 2 1 * *",
                "factory": "modules.mod_settlement_recon.handler:SettlementReconHandler",
                "datasets": ["order", "settlement"],
                "tolerance": "0.01",
                "subscribers": ["owner"],
            },
        ),
        Contribution(
            kind=ContributionKind.GATE_RULE,
            id="gate.s09.report",
            config={"action_code": "S09.report", "gate_level": "L0", "version": "1"},
        ),
        Contribution(
            kind=ContributionKind.WORKBENCH_CARD,
            id="card.recon",
            config={
                "card_id": "card.recon",
                "page_id": "P08",
                "title": "对账与差异",
                "slot": "main",
                "data_endpoint": "/api/v1/settlement/reconciliation",
                "empty_state_copy": "无差异",
                "order": 10,
            },
        ),
        Contribution(
            kind=ContributionKind.HEALTH_CHECK,
            id="health.settlement_recon",
            config={"factory": "modules.mod_settlement_recon.health:probe"},
        ),
        Contribution(
            kind=ContributionKind.CQ,
            id="cq.settlement_recon",
            config={
                "questions": [
                    "Q1 结算金额与期望净额差异是否逐条可追溯",
                    "Q2 财务写入是否仍保持 L3 禁止自动化",
                ]
            },
        ),
    ],
    scenes=["S09"],
    data=[],
    config_namespace="modules.settlement_recon",
    table_prefix="st",
    health_checks=["health.settlement_recon"],
    cq=["cq.settlement_recon"],
    license="MIT",
    owner="studio",
)
