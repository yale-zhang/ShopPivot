"""mod_daily_report：S01 经营日报应用包（M0 唯一业务模块）。

刻意**不**把 mod_platform_pdd 写进 depends：
新增平台时只加一个 adapter 模块，业务模块零改动（表 9-21）。
平台在运行时按数据源解析，缺失即 E008 fail-closed。
"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    CapabilityRequirement,
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
)

METRIC_FILES = [
    "data/metric_cards/uv.yaml",
    "data/metric_cards/pv.yaml",
    "data/metric_cards/paid_orders.yaml",
    "data/metric_cards/gmv.yaml",
    "data/metric_cards/refund_amount.yaml",
    "data/metric_cards/net_gmv.yaml",
    "data/metric_cards/aov.yaml",
    "data/metric_cards/cvr.yaml",
    "data/metric_cards/ad_cost.yaml",
    "data/metric_cards/roi.yaml",
    "data/metric_cards/dsr.yaml",
    "data/metric_cards/inventory_turnover.yaml",
]

manifest = ModuleManifest(
    name="mod_daily_report",
    version="1.2.0",
    category=ModuleCategory.BUSINESS,
    description="S01 经营日报：三级取数 → 标准化脱敏 → 口径计算 → 出报 → 推送 → 归档",
    depends=["mod_core", "mod_worker_headless"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L0",
    requires=[CapabilityRequirement(name="EXPORT_PARSE")],
    provides=[
        Contribution(
            kind=ContributionKind.SCENE_PACKAGE,
            id="scene.s01",
            config={
                "scene": "S01",
                "app_id": "app_demo_daily",
                "cron": "0 8 * * *",
                "factory": "modules.mod_daily_report.handler:DailyReportHandler",
                "gate_action": "S01.report",
                "datasets": ["order", "traffic", "ad", "review", "inventory"],
                "subscribers": ["owner"],
                "thresholds": {"cvr_min": 0.6, "roi_min": 2.0, "dsr_min": 4.5},
            },
        ),
        Contribution(
            kind=ContributionKind.GATE_RULE,
            id="gate.s01.report",
            config={"action_code": "S01.report", "gate_level": "L0", "version": "1"},
        ),
        Contribution(
            kind=ContributionKind.METRIC_CARD,
            id="metrics.daily",
            config={
                "files": METRIC_FILES,
                "metric_codes": [
                    "uv",
                    "pv",
                    "paid_orders",
                    "gmv",
                    "refund_amount",
                    "net_gmv",
                    "aov",
                    "cvr",
                    "ad_cost",
                    "roi",
                    "dsr",
                    "inventory_turnover",
                ],
            },
        ),
        Contribution(
            kind=ContributionKind.WORKBENCH_CARD,
            id="card.daily_report",
            config={
                "card_id": "card.daily_report",
                "page_id": "P01",
                "title": "经营日报",
                "slot": "main",
                "data_endpoint": "/api/v1/reports/latest",
                "empty_state_copy": "该时间窗暂无数据（非取数失败）",
                "order": 10,
            },
        ),
        Contribution(
            kind=ContributionKind.WORKBENCH_CARD,
            id="card.metric_alert",
            config={
                "card_id": "card.metric_alert",
                "page_id": "P01",
                "title": "指标告警",
                "slot": "alert",
                "data_endpoint": "/api/v1/reports/latest/alerts",
                "empty_state_copy": "未命中阈值",
                "order": 20,
            },
        ),
        Contribution(
            kind=ContributionKind.NOTIFICATION_TEMPLATE,
            id="evt01.daily",
            config={
                "event": "EVT-01",
                "title": "经营日报已生成",
                "body": "{platform}/{shop} {window} 日报已生成，run_id {run_id}",
            },
        ),
        Contribution(
            kind=ContributionKind.HEALTH_CHECK,
            id="health.daily_report",
            config={"factory": "modules.mod_daily_report.health:probe"},
        ),
        Contribution(
            kind=ContributionKind.CQ,
            id="cq.daily_report",
            config={
                "questions": [
                    "Q1 昨天各店 GMV 与人工核对是否一致",
                    "Q2 转化率分母为零时是否标注不适用",
                ]
            },
        ),
    ],
    scenes=["S01"],
    data=METRIC_FILES,
    config_namespace="modules.daily_report",
    table_prefix="mr",
    health_checks=["health.daily_report"],
    cq=["cq.daily_report"],
    license="MIT",
    owner="studio",
)
