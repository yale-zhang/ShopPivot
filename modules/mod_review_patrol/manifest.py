"""mod_review_patrol：S05 评价 / 差评 / 买家问答巡检（M1）。

只读采集 + 内部工单（L1）；回复话术仍由人写，平台不自动回复。
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
    name="mod_review_patrol",
    version="0.9.0",
    category=ModuleCategory.BUSINESS,
    description="S05 评价巡检：负向评价识别 → 去重工单 → SLA 派单 → DSR 跟踪",
    depends=["mod_core", "mod_worker_headless"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L1",
    requires=[CapabilityRequirement(name="EXPORT_PARSE")],
    provides=[
        Contribution(
            kind=ContributionKind.SCENE_PACKAGE,
            id="scene.s05",
            config={
                "scene": "S05",
                "app_id": "app_demo_review",
                "cron": "0 10 * * *",
                "factory": "modules.mod_review_patrol.handler:ReviewPatrolHandler",
                "gate_action": "S05.ticket",
                "datasets": ["review"],
                "sla_hours": 24,
                "rules": {
                    "rating_threshold": 3,
                    "high_severity_max": 2,
                    "keywords": ["破损", "差评", "退货", "假货", "欺诈", "发错"],
                },
                "subscribers": ["editor"],
            },
        ),
        Contribution(
            kind=ContributionKind.GATE_RULE,
            id="gate.s05.ticket",
            config={"action_code": "S05.ticket", "gate_level": "L1", "version": "1"},
        ),
        Contribution(
            kind=ContributionKind.WORKBENCH_CARD,
            id="card.review_todo",
            config={
                "card_id": "card.review_todo",
                "page_id": "P02",
                "title": "差评与问答工单",
                "slot": "main",
                "data_endpoint": "/api/v1/reviews/tickets",
                "empty_state_copy": "已清零",
                "order": 10,
            },
        ),
        Contribution(
            kind=ContributionKind.NOTIFICATION_TEMPLATE,
            id="evt03.review",
            config={
                "event": "EVT-03",
                "title": "差评工单待处理",
                "body": "{platform}/{shop} 评价 {review_id} 命中 {hit_rule}，SLA {sla_due_at}",
            },
        ),
        Contribution(
            kind=ContributionKind.HEALTH_CHECK,
            id="health.review_patrol",
            config={"factory": "modules.mod_review_patrol.health:probe"},
        ),
        Contribution(
            kind=ContributionKind.CQ,
            id="cq.review_patrol",
            config={
                "questions": [
                    "Q1 同一评价重复巡检是否会产生第二条工单",
                    "Q2 超 SLA 未派单是否升级通知",
                ]
            },
        ),
    ],
    scenes=["S05"],
    data=[],
    config_namespace="modules.review_patrol",
    table_prefix="rvp",
    health_checks=["health.review_patrol"],
    cq=["cq.review_patrol"],
    license="MIT",
    owner="studio",
)
