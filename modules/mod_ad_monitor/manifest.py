"""mod_ad_monitor：S04 投放归集与投产比预警（只读，不自动调价/调预算）。"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    CapabilityRequirement,
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
)

manifest = ModuleManifest(
    name="mod_ad_monitor",
    version="0.5.0",
    category=ModuleCategory.BUSINESS,
    description="S04 投放归集：花费/成交/投产比 → 阈值预警 → 调优建议（不触发写入）",
    depends=["mod_core", "mod_worker_headless"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L0",
    requires=[CapabilityRequirement(name="EXPORT_PARSE")],
    provides=[
        Contribution(
            kind=ContributionKind.SCENE_PACKAGE,
            id="scene.s04",
            config={
                "gate_action": "S04.report",
                "scene": "S04",
                "app_id": "app_demo_ads",
                "cron": "0 11 * * *",
                "factory": "modules.mod_ad_monitor.handler:AdMonitorHandler",
                "datasets": ["ad"],
                "roi_min": 2.0,
                "watch_min": 1.0,
                "subscribers": ["owner"],
            },
        ),
        Contribution(
            kind=ContributionKind.GATE_RULE,
            id="gate.s04.report",
            config={"action_code": "S04.report", "gate_level": "L0", "version": "1"},
        ),
        Contribution(
            kind=ContributionKind.WORKBENCH_CARD,
            id="card.ad_roi",
            config={
                "card_id": "card.ad_roi",
                "page_id": "P04",
                "title": "投放归集与投产比",
                "slot": "main",
                "data_endpoint": "/api/v1/ads/summary",
                "empty_state_copy": "当前无投放数据",
                "order": 10,
            },
        ),
        Contribution(
            kind=ContributionKind.NOTIFICATION_TEMPLATE,
            id="evt02.ad",
            config={
                "event": "EVT-02",
                "title": "投产比预警",
                "body": "{platform}/{shop} 计划 {campaign} 投产比 {roi} 低于阈值 {threshold}",
            },
        ),
        Contribution(
            kind=ContributionKind.HEALTH_CHECK,
            id="health.ad_monitor",
            config={"factory": "modules.mod_ad_monitor.health:probe"},
        ),
        Contribution(
            kind=ContributionKind.CQ,
            id="cq.ad_monitor",
            config={"questions": ["Q1 投产比是否按计划汇总", "Q2 预警是否只出建议、不自动调价"]},
        ),
    ],
    scenes=["S04"],
    data=[],
    config_namespace="modules.ad_monitor",
    table_prefix="ad",
    health_checks=["health.ad_monitor"],
    cq=["cq.ad_monitor"],
    license="MIT",
    owner="studio",
)
