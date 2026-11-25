"""FastAPI 依赖：会话用户、机器 token、角色与 shop_scope 校验。"""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, Request

from bootstrap.container import AppContainer
from kernel.contexts.identity.domain.account import (
    Account,
    Permission,
    Role,
    ShopScope,
    has_permission,
)
from kernel.contexts.identity.infrastructure.auth import JwtCodec
from shared.errors.registry import DomainError


@dataclass
class SessionUser:
    username: str
    role: Role
    shops: list[ShopScope] = field(default_factory=list)

    @property
    def is_owner(self) -> bool:
        return self.role is Role.OWNER

    def can(self, permission: Permission) -> bool:
        return has_permission(self.role, permission)


def get_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise DomainError("E008", "应用容器尚未初始化")
    return container


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def get_current_user(
    request: Request, container: AppContainer = Depends(get_container)
) -> SessionUser:
    token = _bearer(request)
    if not token:
        raise DomainError("E002", "缺少会话令牌")
    codec = JwtCodec(container.settings.jwt_secret, container.settings.jwt_ttl_minutes)
    payload = codec.decode(token)
    shops = [
        ShopScope(platform=str(item.split(":", 1)[0]), shop_id=str(item.split(":", 1)[1]))
        for item in payload.get("shops", [])
        if ":" in item
    ]
    return SessionUser(
        username=str(payload.get("sub", "")),
        role=Role(payload.get("role", "VIEWER")),
        shops=shops,
    )


def require(permission: Permission):
    def dependency(user: SessionUser = Depends(get_current_user)) -> SessionUser:
        if not user.can(permission):
            raise DomainError(
                "E003",
                f"角色 {user.role.value} 无权限: {permission.value}",
            )
        return user

    return dependency


def require_owner(user: SessionUser = Depends(get_current_user)) -> SessionUser:
    if user.role is not Role.OWNER:
        raise DomainError("E003", "该操作仅 OWNER 可执行")
    return user


def get_machine_token_scope(
    request: Request, container: AppContainer = Depends(get_container)
) -> str:
    token = request.headers.get("x-api-token", "").strip()
    if not token:
        raise DomainError("E002", "缺少 X-Api-Token")
    scope = container.api_tokens.resolve(token)
    if scope is None:
        raise DomainError("E002", "机器 token 无效或已禁用")
    return scope


def assert_shop_scope(user: SessionUser, platform: str, shop_id: str) -> None:
    if user.is_owner:
        return
    if not any(item.platform == platform and item.shop_id == shop_id for item in user.shops):
        raise DomainError(
            "E003",
            f"无权访问店铺 {platform}/{shop_id}",
            details={"platform": platform, "shop_id": shop_id},
        )


def account_to_session(account: Account, shops: list[ShopScope]) -> SessionUser:
    return SessionUser(username=account.username, role=account.role, shops=shops)
