"""身份权限（BC-7）：3 角色 + shop_scope + 机器 token，不做多租户。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from shared.errors.registry import DomainError


class Role(str, Enum):
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"

    @property
    def rank(self) -> int:
        return {"VIEWER": 1, "EDITOR": 2, "OWNER": 3}[self.value]


class Permission(str, Enum):
    VIEW_WORKBENCH = "view_workbench"
    EXPORT_REPORT = "export_report"
    APPROVE_L2 = "approve_l2"
    MANAGE_MODULES = "manage_modules"
    VIEW_AUDIT = "view_audit"
    VIEW_RAW_PII = "view_raw_pii"
    MANAGE_SUBSCRIPTIONS = "manage_subscriptions"
    TRIGGER_RUN = "trigger_run"
    HANDLE_TODO = "handle_todo"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset(
        {Permission.VIEW_WORKBENCH, Permission.EXPORT_REPORT}
    ),
    Role.EDITOR: frozenset(
        {
            Permission.VIEW_WORKBENCH,
            Permission.EXPORT_REPORT,
            Permission.APPROVE_L2,
            Permission.MANAGE_SUBSCRIPTIONS,
            Permission.TRIGGER_RUN,
            Permission.HANDLE_TODO,
        }
    ),
    Role.OWNER: frozenset(Permission),
}


def has_permission(role: Role | str, permission: Permission) -> bool:
    resolved = role if isinstance(role, Role) else Role(role)
    return permission in ROLE_PERMISSIONS[resolved]


def require_permission(role: Role | str, permission: Permission) -> None:
    if not has_permission(role, permission):
        raise DomainError(
            "E003",
            f"角色 {role} 无权限: {permission.value}",
            details={"role": str(role), "permission": permission.value},
        )


@dataclass(frozen=True, slots=True)
class ShopScope:
    platform: str
    shop_id: str

    @property
    def key(self) -> str:
        return f"{self.platform}:{self.shop_id}"


@dataclass
class Account:
    id: int
    username: str
    display_name: str
    role: Role
    enabled: bool = True


class AccountRepository(Protocol):
    def by_username(self, username: str) -> tuple[Account, str] | None:
        """返回 (账号, 密码哈希)。"""
        ...

    def add(self, username: str, display_name: str, password_hash: str, role: Role) -> Account: ...

    def shops(self, account_id: int) -> list[ShopScope]: ...


class ApiTokenRepository(Protocol):
    def register(self, name: str, token: str, scope: str) -> None: ...

    def resolve(self, token: str) -> str | None:
        """返回 token 的 scope（READONLY / SUGGEST），未知返回 None。"""
        ...
