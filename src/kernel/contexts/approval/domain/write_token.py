"""一次性 WriteToken（短时效、绑定 task_id，只有闸门能签发）。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from shared.errors.registry import DomainError


@dataclass(frozen=True, slots=True)
class WriteToken:
    token: str
    task_id: str
    issued_at: datetime
    expires_at: datetime
    ttl_seconds: int = 300

    @classmethod
    def issue(cls, task_id: str, now: datetime, ttl_seconds: int = 300) -> "WriteToken":
        if not task_id:
            raise DomainError("E007", "WriteToken 必须绑定 task_id")
        if ttl_seconds <= 0 or ttl_seconds > 900:
            raise DomainError("E007", f"WriteToken 时效非法: {ttl_seconds}s")
        return cls(
            token=f"wt_{uuid4().hex}",
            task_id=task_id,
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            ttl_seconds=ttl_seconds,
        )

    def is_valid(self, task_id: str, now: datetime) -> bool:
        return self.task_id == task_id and now <= self.expires_at

    def assert_valid(self, task_id: str, now: datetime) -> None:
        if self.task_id != task_id:
            raise DomainError("E007", "WriteToken 与 task_id 不匹配")
        if now > self.expires_at:
            raise DomainError("E007", "WriteToken 已过期，不得重放")
