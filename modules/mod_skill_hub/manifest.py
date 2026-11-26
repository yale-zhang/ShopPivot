"""mod_skill_hub：技能目录/运行记录只读视图（S0）。"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
)

manifest = ModuleManifest(
    name="mod_skill_hub",
    version="0.5.0",
    category=ModuleCategory.CAPABILITY,
    description="技能中心：Skill 目录、信任等级、能力与运行记录（只读 S0）",
    depends=["mod_core"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L2",
    provides=[
        Contribution(
            kind=ContributionKind.WORKBENCH_CARD,
            id="card.skills",
            config={
                "card_id": "card.skills",
                "page_id": "P14",
                "title": "技能中心",
                "slot": "main",
                "data_endpoint": "/api/v1/skills/catalog",
                "empty_state_copy": "暂无已登记 Skill",
                "order": 10,
            },
        ),
        Contribution(
            kind=ContributionKind.HEALTH_CHECK,
            id="health.skill_hub",
            config={"factory": "modules.mod_skill_hub.health:probe"},
        ),
        Contribution(
            kind=ContributionKind.CQ,
            id="cq.skill_hub",
            config={"questions": ["Q1 Skill 是否锁定版本与信任等级", "Q2 运行记录是否可追溯"]},
        ),
    ],
    scenes=[],
    data=[],
    config_namespace="modules.skill_hub",
    table_prefix="sk",
    health_checks=["health.skill_hub"],
    cq=["cq.skill_hub"],
    license="MIT",
    owner="studio",
)
