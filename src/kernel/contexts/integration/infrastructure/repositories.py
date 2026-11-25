"""通知去重与回执记录。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from kernel.contexts.integration.domain.notification import (
    NotificationLogRepository,
    NotificationMessage,
)
from kernel.persistence.base import Database, iso_or_none, utcnow
from kernel.contexts.integration.domain.subscription import Subscription
from kernel.persistence.tables import NotificationLogRow, SubscriptionRow
from shared.errors.registry import DomainError


class SqlNotificationLogRepository(NotificationLogRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def add_if_absent(self, message: NotificationMessage) -> bool:
        try:
            with self.db.session() as session:
                session.add(
                    NotificationLogRow(
                        event=message.event,
                        receiver=message.receiver,
                        channel=message.channel,
                        dedupe_key=message.dedupe_key,
                        payload={
                            "title": message.title,
                            "body": message.body,
                            **message.payload,
                        },
                        status="SENT",
                        sent_at=utcnow(),
                    )
                )
            return True
        except IntegrityError:
            return False

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(NotificationLogRow)
                .order_by(NotificationLogRow.id.desc())
                .limit(limit)
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "event": row.event,
                    "receiver": row.receiver,
                    "channel": row.channel,
                    "dedupe_key": row.dedupe_key,
                    "status": row.status,
                    "sent_at": iso_or_none(row.sent_at),
                    "payload": row.payload,
                }
                for row in rows
            ]


class SqlSubscriptionRepository:
    def __init__(self, database: Database) -> None:
        self.db = database

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
    ) -> int:
        try:
            with self.db.session() as session:
                row = SubscriptionRow(
                    name=name,
                    event=event,
                    receiver=receiver,
                    channel=channel,
                    window=window,
                    thresholds=thresholds or {},
                    silent_window=silent_window,
                    enabled=True,
                )
                session.add(row)
                session.flush()
                return int(row.id)
        except IntegrityError as exc:
            raise DomainError("E006", f"订阅已存在: {event}/{receiver}") from exc

    def all(self) -> list[Subscription]:
        with self.db.session() as session:
            rows = session.execute(select(SubscriptionRow)).scalars().all()
            return [self._to_domain(row) for row in rows]

    def delete(self, subscription_id: int) -> bool:
        with self.db.session() as session:
            row = session.get(SubscriptionRow, subscription_id)
            if row is None:
                return False
            session.delete(row)
            return True

    def receivers_for(self, event: str) -> list[str]:
        with self.db.session() as session:
            rows = session.execute(
                select(SubscriptionRow).where(
                    SubscriptionRow.event == event,
                    SubscriptionRow.enabled.is_(True),
                )
            ).scalars().all()
            return [row.receiver for row in rows]

    @staticmethod
    def _to_domain(row: SubscriptionRow) -> Subscription:
        return Subscription(
            subscription_id=row.id,
            name=row.name,
            event=row.event,
            receiver=row.receiver,
            channel=row.channel,
            window=row.window,
            thresholds=row.thresholds or {},
            silent_window=row.silent_window,
            enabled=row.enabled,
        )
