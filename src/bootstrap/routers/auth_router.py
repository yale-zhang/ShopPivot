"""登录与会话。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from bootstrap.container import AppContainer
from bootstrap.deps import SessionUser, get_container, get_current_user
from kernel.contexts.identity.infrastructure.auth import JwtCodec, verify_password
from kernel.contexts.observability.domain.models import AuditEntry
from shared.errors.registry import DomainError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
def login(body: LoginRequest, container: AppContainer = Depends(get_container)) -> dict:
    found = container.accounts.by_username(body.username)
    if found is None or not verify_password(body.password, found[1]):
        raise DomainError("E002", "用户名或口令错误")
    account, _ = found
    shops = container.accounts.shops(account.id)
    codec = JwtCodec(container.settings.jwt_secret, container.settings.jwt_ttl_minutes)
    token = codec.encode(
        username=account.username,
        role=account.role.value,
        shop_scopes=[scope.key for scope in shops],
    )
    container.audit.record(
        AuditEntry(
            actor=account.username,
            action="auth.login",
            object_type="account",
            object_id=account.username,
        )
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": account.role.value,
        "display_name": account.display_name,
        "shops": [{"platform": s.platform, "shop_id": s.shop_id} for s in shops],
    }


@router.get("/me")
def me(user: SessionUser = Depends(get_current_user)) -> dict:
    return {
        "username": user.username,
        "role": user.role.value,
        "shops": [{"platform": s.platform, "shop_id": s.shop_id} for s in user.shops],
    }
