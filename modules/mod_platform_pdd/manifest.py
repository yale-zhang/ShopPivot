"""mod_platform_pdd：拼多多适配器（M0 仅落地导出通道 + OpenAPI 骨架）。

授权与字段权限未到位时 **不猜测、不抓网页**：
OpenAPI 通道直接不可用 → 降级到后台导出；导出也没有 → E004 fail-closed。
"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    CapabilityRequirement,
    Contribution,
    ContributionKind,
    CredentialScope,
    DataContractRequirement,
    ModuleCategory,
    ModuleManifest,
)

manifest = ModuleManifest(
    name="mod_platform_pdd",
    version="1.0.0",
    category=ModuleCategory.ADAPTER,
    description="拼多多后台导出 + OpenAPI 骨架（字段映射/枚举/限流）",
    depends=[],
    api_compat=">=1.0,<2.0",
    gate_level_max="L0",
    requires=[
        CapabilityRequirement(name="EXPORT_PARSE"),
        CapabilityRequirement(name="FETCH_HTTP"),
        CredentialScope(scope="pdd:report:read"),
        DataContractRequirement(dataset="pdd.order.daily", version="1"),
    ],
    provides=[
        Contribution(
            kind=ContributionKind.PLATFORM_ADAPTER,
            id="pdd",
            config={
                "platform": "pdd",
                "factory": "modules.mod_platform_pdd.adapter:PddPlatformAdapter",
                "datasets": ["order", "traffic", "ad", "review", "inventory"],
                "rate_limit_per_min": 60,
            },
        ),
        Contribution(
            kind=ContributionKind.DATA_CONTRACT,
            id="pdd.order.daily",
            config={
                "dataset": "pdd.order.daily",
                "version": "1",
                "platform": "pdd",
                "required_fields": ["order_id", "stat_date", "paid_amount", "status"],
                "enum_sets": {"status": ["PAID", "REFUNDED", "CLOSED"]},
                "quality_tests": ["status 必须在枚举集内", "order_id 唯一"],
            },
        ),
    ],
    data=[],
    config_namespace="modules.platform_pdd",
    table_prefix="ppdd",
    license="MIT",
)
