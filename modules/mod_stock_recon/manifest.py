"""mod_stock_recon：S07 库存核对与补货预警（M1）。

平台 / ERP / WMS 三方可售按 SKU 对齐，差异分级并输出补货建议；
只出建议，不自动下单、不自动改库存。
"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    CapabilityRequirement,
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
)

manifest = ModuleManifest(
    name="mod_stock_recon",
    version="0.9.0",
    category=ModuleCategory.BUSINESS,
    description="S07 库存核对：三方可售对齐 → 断货/超卖/滞销 → 补货建议",
    depends=["mod_core", "mod_worker_headless"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L1",
    requires=[CapabilityRequirement(name="EXPORT_PARSE")],
    provides=[
        Contribution(
            kind=ContributionKind.SCENE_PACKAGE,
            id="scene.s07",
            config={
                "scene": "S07",
                "app_id": "app_demo_stock",
                "cron": "0 9 * * *",
                "factory": "modules.mod_stock_recon.handler:StockReconHandler",
                "gate_action": "S07.suggestion",
                "datasets": ["inventory", "erp_inventory", "wms_inventory"],
                "tolerance": 5,
                "slow_threshold": 100,
                "safety_stock": 20,
                "subscribers": ["owner"],
            },
        ),
        Contribution(
            kind=ContributionKind.GATE_RULE,
            id="gate.s07.suggestion",
            config={"action_code": "S07.suggestion", "gate_level": "L1", "version": "1"},
        ),
        Contribution(
            kind=ContributionKind.WORKBENCH_CARD,
            id="card.stock_alert",
            config={
                "card_id": "card.stock_alert",
                "page_id": "P03",
                "title": "库存差异与补货预警",
                "slot": "main",
                "data_endpoint": "/api/v1/inventory/reconciliation",
                "empty_state_copy": "三方库存一致，无差异",
                "order": 10,
            },
        ),
        Contribution(
            kind=ContributionKind.NOTIFICATION_TEMPLATE,
            id="evt04.stock",
            config={
                "event": "EVT-04",
                "title": "库存差异预警",
                "body": "{platform}/{shop} 存在 {counts} 条库存差异，补货建议 {suggestions} 条",
            },
        ),
        Contribution(
            kind=ContributionKind.HEALTH_CHECK,
            id="health.stock_recon",
            config={"factory": "modules.mod_stock_recon.health:probe"},
        ),
        Contribution(
            kind=ContributionKind.CQ,
            id="cq.stock_recon",
            config={
                "questions": [
                    "Q1 三方快照时间不一致时是否分别标注",
                    "Q2 断货建议是否只出清单、不下单",
                ]
            },
        ),
    ],
    scenes=["S07"],
    data=[],
    config_namespace="modules.stock_recon",
    table_prefix="sr",
    health_checks=["health.stock_recon"],
    cq=["cq.stock_recon"],
    license="MIT",
    owner="studio",
)
