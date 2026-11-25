"""通知服务：去重 + 通道分发（CMP-005 / EVT-01~10）。"""
from __future__ import annotations

import logging
from typing import Any, Mapping

from kernel.contexts.integration.domain.notification import (
    NotificationChannel,
    NotificationLogRepository,
    NotificationMessage,
)

log = logging.getLogger("shoppivot.notification")


class NotificationService:
    def __init__(
        self,
        repo: NotificationLogRepository,
        channels: Mapping[str, NotificationChannel],
        *,
        default_channel: str = "CONSOLE",
    ) -> None:
        self.repo = repo
        self.channels = dict(channels)
        self.default_channel = default_channel

    def send(
        self,
        *,
        event: str,
        receiver: str,
        title: str,
        body: str,
        dedupe_key: str,
        channel: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        message = NotificationMessage(
            event=event,
            receiver=receiver,
            channel=channel or self.default_channel,
            title=title,
            body=body,
            dedupe_key=dedupe_key,
            payload=payload or {},
        )
        if not self.repo.add_if_absent(message):
            log.info("notification deduplicated", extra={"event": event, "receiver": receiver})
            return False
        target = self.channels.get(message.channel)
        if target is None:
            log.warning("notification channel missing", extra={"channel": message.channel})
            return False
        return target.send(message)


class ConsoleNotificationChannel:
    name = "CONSOLE"

    def send(self, message: NotificationMessage) -> bool:
        log.info(
            "notification sent",
            extra={
                "event": message.event,
                "receiver": message.receiver,
                "title": message.title,
                "body": message.body,
                "dedupe_key": message.dedupe_key,
            },
        )
        return True
