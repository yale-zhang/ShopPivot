"""mod_core：Kernel 之上的默认能力（权限种子、通知模板、审计健康检查）。

core 模块不可禁用（loader 强制），且不依赖任何业务模块。
"""
from __future__ import annotations

from kernel.contracts.manifest_schema import (
    Contribution,
    ContributionKind,
    Hooks,
    ModuleCategory,
    ModuleManifest,
)

_PERMISSIONS = [
    ("perm.owner", "OWNER", "*"),
    ("perm.editor", "EDITOR", "view_workbench,export_report,approve_l2,trigger_run"),
    ("perm.viewer", "VIEWER", "view_workbench,export_report"),
]

manifest = ModuleManifest(
    name="mod_core",
    version="1.0.0",
    category=ModuleCategory.CORE,
    description="默认权限、通知模板与基础健康检查",
    depends=[],
    api_compat=">=1.0,<2.0",
    gate_level_max="L0",
    provides=[
        Contribution(
            kind=ContributionKind.PERMISSION,
            id=perm_id,
            config={"role": role, "capabilities": caps},
        )
        for perm_id, role, caps in _PERMISSIONS
    ]
    + [
        Contribution(
            kind=ContributionKind.NOTIFICATION_TEMPLATE,
            id="evt07.exception",
            config={
                "event": "EVT-07",
                "title": "执行异常",
                "body": "运行 {run_id} 在 {node_id} 失败：{err_code}/{err_layer}",
            },
        ),
        Contribution(
            kind=ContributionKind.HEALTH_CHECK,
            id="health.core",
            config={"factory": "modules.mod_core.health:permission_table_check"},
        ),
    ],
    scenes=[],
    data=["security/permissions.csv"],
    config_namespace="modules.core",
    table_prefix="core",
    hooks=Hooks(on_startup="modules.mod_core.hooks:on_startup"),
    health_checks=["health.core"],
    cq=["Q1 三个角色的权限矩阵与文档一致", "Q2 审计表只增不改"],
    license="MIT",
    owner="studio",
)
