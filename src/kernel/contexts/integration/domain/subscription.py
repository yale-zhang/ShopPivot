"""订阅与通知模板（P12 / 表 3-27）。

订阅对象 = 报表模板 + 接收人 + 渠道 + 时间窗 + 阈值；退订与静默窗口可配置，
通知去重按 event_id + 接收人（由 NotificationService 的 dedupe_key 承担）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Subscription:
    subscription_id: int
    name: str
    event: str
    receiver: str
    channel: str = "CONSOLE"
    window: str = "昨日"
    thresholds: dict[str, float] | None = None
    silent_window: str | None = None
    enabled: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.subscription_id,
            "name": self.name,
            "event": self.event,
            "receiver": self.receiver,
            "channel": self.channel,
            "window": self.window,
            "thresholds": self.thresholds or {},
            "silent_window": self.silent_window,
            "enabled": self.enabled,
        }
