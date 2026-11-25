"""mod_campaign_apply：S03 活动提报（L2 写入动作）。

生成提报清单 → 人工确认 → 提交活动报名 → 回查台账；重复提报必须阻断。
"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
)

manifest = ModuleManifest(
    name="mod_campaign_apply",
    version="0.5.0",
    category=ModuleCategory.BUSINESS,
    description="S03 活动提报：资格/价格/库存/互斥/重复五项校验 → 人工确认 → 提交 → 回查",
    depends=["mod_core"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L2",
    provides=[
        Contribution(
            kind=ContributionKind.WRITE_ACTION,
            id="s03.campaign_apply",
            config={
                "action_code": "S03.campaign_apply",
                "scene": "S03",
                "factory": "modules.mod_campaign_apply.handler:CampaignApplyAction",
                "description": "活动提报报名（L2）",
            },
        ),
        Contribution(
            kind=ContributionKind.GATE_RULE,
            id="gate.s03.campaign_apply",
            config={"action_code": "S03.campaign_apply", "gate_level": "L2", "version": "1"},
        ),
        Contribution(
            kind=ContributionKind.HEALTH_CHECK,
            id="health.campaign_apply",
            config={"factory": "modules.mod_campaign_apply.health:probe"},
        ),
        Contribution(
            kind=ContributionKind.CQ,
            id="cq.campaign_apply",
            config={
                "questions": [
                    "Q1 同一活动+商品重复提报是否被阻断",
                    "Q2 活动价高于日常价是否禁止提交",
                ]
            },
        ),
    ],
    scenes=["S03"],
    data=[],
    config_namespace="modules.campaign_apply",
    table_prefix="ca",
    health_checks=["health.campaign_apply"],
    cq=["cq.campaign_apply"],
    license="MIT",
    owner="studio",
)
