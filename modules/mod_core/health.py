"""mod_core 健康检查（零参数工厂）。"""
from __future__ import annotations

from kernel.contexts.identity.domain.account import ROLE_PERMISSIONS, Role


def permission_table_check() -> tuple[bool, str]:
    for role in Role:
        if not ROLE_PERMISSIONS.get(role):
            return False, f"角色 {role.value} 没有权限定义"
    return True, ""
