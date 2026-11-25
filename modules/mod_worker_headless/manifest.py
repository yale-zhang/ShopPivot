"""mod_worker_headless：无桌面执行通道（M0 唯一执行通道）。"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
)


def _cap(capability: str, description: str) -> Contribution:
    return Contribution(
        kind=ContributionKind.WORKER_CAPABILITY,
        id=f"cap.{capability.lower()}",
        config={
            "capability": capability,
            "description": description,
            "factory": "modules.mod_worker_headless.capability:HeadlessCapability",
        },
    )


manifest = ModuleManifest(
    name="mod_worker_headless",
    version="1.0.0",
    category=ModuleCategory.CAPABILITY,
    description="HTTP 取数 / 导出解析 / SQL / 文件系统，无桌面会话",
    depends=["mod_core"],
    api_compat=">=1.0,<2.0",
    gate_level_max="L0",
    provides=[
        _cap("FETCH_HTTP", "官方开放接口取数"),
        _cap("EXPORT_PARSE", "后台导出 CSV/Excel 解析"),
        _cap("SQL", "参数化只读 SQL 计算"),
        _cap("FS", "受控文件读写"),
    ],
    data=[],
    config_namespace="modules.worker_headless",
    table_prefix="whl",
    license="Apache-2.0",
)
