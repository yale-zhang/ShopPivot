"""bundle_daily_ops：日常运营组合包（只声明依赖，不含业务逻辑）。"""
from __future__ import annotations

from kernel.contracts.manifest_schema import ModuleCategory, ModuleManifest

manifest = ModuleManifest(
    name="bundle_daily_ops",
    version="1.0.0",
    category=ModuleCategory.BUNDLE,
    description="日常运营包：日报 + 评价巡检 + 库存对账（一键装配）",
    depends=[
        "mod_core",
        "mod_worker_headless",
        "mod_platform_demo",
        "mod_platform_pdd",
        "mod_daily_report",
        "mod_review_patrol",
        "mod_stock_recon",
    ],
    api_compat=">=1.0,<2.0",
    gate_level_max="L1",
    data=[],
    config_namespace="modules.bundle_daily_ops",
    table_prefix="bdo",
    license="MIT",
    owner="studio",
    auto_install=False,
)
