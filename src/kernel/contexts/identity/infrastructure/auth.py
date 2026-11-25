"""口令与令牌工具：PBKDF2 口令哈希、JWT 会话、机器 token 摘要。

M0 不依赖外部 IAM；凭据明文不落库，机器 token 只存 sha256。
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from shared.errors.registry import DomainError

_ITERATIONS = 120_000


def hash_password(password: str, *, iterations: int = _ITERATIONS) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return f"pbkdf2${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_api_token() -> str:
    return f"spat_{secrets.token_urlsafe(32)}"


class JwtCodec:
    def __init__(self, secret: str, ttl_minutes: int = 480) -> None:
        if not secret:
            raise ValueError("JWT secret 不能为空")
        self.secret = secret
        self.ttl_minutes = ttl_minutes

    def encode(self, *, username: str, role: str, shop_scopes: list[str]) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": username,
            "role": role,
            "shops": shop_scopes,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self.ttl_minutes)).timestamp()),
        }
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, self.secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as exc:
            raise DomainError("E002", "会话已过期，请重新登录") from exc
        except jwt.InvalidTokenError as exc:
            raise DomainError("E002", "会话令牌无效") from exc
