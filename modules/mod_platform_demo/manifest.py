"""mod_platform_demo：确定性数据源（仅用于 M0 端到端验证，非生产平台接入）。

为什么需要它：M0 要求"单平台单店铺 1 套官方接口或定时导出"，但店铺授权周期不可控。
demo 适配器走三级取数的第 2 级（后台导出），用 fixtures 充当导出文件，
所有断言（口径、脱敏、run_id、fail-closed）与 pdd 适配器完全一致。
"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    Contribution,
    ContributionKind,
    DataContractRequirement,
    CapabilityRequirement,
    ModuleCategory,
    ModuleManifest,
)

manifest = ModuleManifest(
    name="mod_platform_demo",
    version="1.0.0",
    category=ModuleCategory.ADAPTER,
    description="确定性 fixture 适配器（M0 演示与测试专用）",
    depends=[],
    api_compat=">=1.0,<2.0",
    gate_level_max="L0",
    requires=[
        CapabilityRequirement(name="EXPORT_PARSE"),
        DataContractRequirement(dataset="demo.order.daily", version="1"),
    ],
    provides=[
        Contribution(
            kind=ContributionKind.PLATFORM_ADAPTER,
            id="demo",
            config={
                "platform": "demo",
                "factory": "modules.mod_platform_demo.adapter:DemoPlatformAdapter",
                "datasets": ["order", "traffic", "ad", "review", "inventory"],
            },
        ),
        Contribution(
            kind=ContributionKind.DATA_CONTRACT,
            id="demo.order.daily",
            config={
                "dataset": "demo.order.daily",
                "version": "1",
                "platform": "demo",
                "required_fields": ["order_id", "stat_date", "paid_amount"],
                "enum_sets": {"status": ["PAID", "REFUNDED", "CLOSED"]},
                "quality_tests": ["order_id 唯一", "paid_amount 非负"],
            },
        ),
    ],
    data=[],
    config_namespace="modules.platform_demo",
    table_prefix="pdemo",
    license="MIT",
)
