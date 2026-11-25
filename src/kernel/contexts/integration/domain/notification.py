"""通知端口（CMP-005 / 表 3-27）。

通知只把待办与建议送到人面前，不做任何写入。
去重键由调用方给出：日报 = run_id + 模板 + 接收人；告警 = 指标 + 时间窗 + 接收人。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    event: str
    receiver: str
    channel: str
    title: str
    body: str
    dedupe_key: str
    payload: dict[str, Any] = field(default_factory=dict)


class NotificationChannel(Protocol):
    name: str

    def send(self, message: NotificationMessage) -> bool: ...


class SubscriptionRepository(Protocol):
    def add(
        self,
        *,
        name: str,
        event: str,
        receiver: str,
        channel: str,
        window: str,
        thresholds: dict[str, float] | None,
        silent_window: str | None,
    ) -> int: ...

    def all(self) -> list[Any]: ...

    def delete(self, subscription_id: int) -> bool: ...

    def receivers_for(self, event: str) -> list[str]: ...


class NotificationLogRepository(Protocol):
    def add_if_absent(self, message: NotificationMessage) -> bool: ...

    def recent(self, limit: int = 50) -> list[dict[str, Any]]: ...
