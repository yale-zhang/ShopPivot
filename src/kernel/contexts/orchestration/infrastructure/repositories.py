"""编排上下文仓储与 Outbox。"""
from __future__ import annotations

import logging
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from kernel.contexts.orchestration.domain.events import DomainEvent
from kernel.contexts.orchestration.domain.ports import EventPublisher, IdempotencyStore, RunRepository
from kernel.contexts.orchestration.domain.run import (
    NodeExecution,
    NodeStatus,
    Run,
    RunStatus,
)
from kernel.persistence.base import Database, as_utc, utcnow
from kernel.persistence.tables import IdempotencyKeyRow, NodeExecutionRow, OutboxEvent, RunInstance
from shared.gate_level import GateLevel
from shared.run_id import RunId
from shared.types.values import Channel, StatWindow

log = logging.getLogger("shoppivot.outbox")


class SqlRunRepository(RunRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def add(self, run: Run) -> None:
        with self.db.session() as session:
            session.add(self._to_row(run))
            for node in run.nodes:
                session.add(self._node_row(run, node))

    def save(self, run: Run) -> None:
        with self.db.session() as session:
            row = session.get(RunInstance, run.run_id.value)
            if row is None:
                session.add(self._to_row(run))
            else:
                self._apply(row, run)
            session.query(NodeExecutionRow).filter(
                NodeExecutionRow.run_id == run.run_id.value
            ).delete()
            for node in run.nodes:
                session.add(self._node_row(run, node))

    def get(self, run_id: RunId) -> Run | None:
        with self.db.session() as session:
            row = session.get(RunInstance, run_id.value)
            if row is None:
                return None
            nodes = session.execute(
                select(NodeExecutionRow).where(NodeExecutionRow.run_id == run_id.value)
            ).scalars().all()
            return self._to_domain(row, nodes)

    def recent(self, limit: int = 20) -> list[Run]:
        with self.db.session() as session:
            rows = session.execute(
                select(RunInstance).order_by(RunInstance.created_at.desc()).limit(limit)
            ).scalars().all()
            return [self._to_domain(row, []) for row in rows]

    # ------------------------------------------------------------------ mapping
    @staticmethod
    def _to_row(run: Run) -> RunInstance:
        return RunInstance(
            run_id=run.run_id.value,
            app_id=run.app_id,
            scene=run.scene,
            platform=run.platform,
            shop_id=run.shop_id,
            window_start=run.window.start,
            window_end=run.window.end,
            trigger_type=run.trigger_type,
            status=run.status.value,
            gate_level_max=run.gate_level_max.value,
            config_snapshot=run.config_snapshot.to_dict(),
            config_snapshot_hash=run.config_snapshot.hash,
            requested_by=run.requested_by,
            started_at=run.started_at,
            ended_at=run.ended_at,
            err_code=run.err_code,
            err_layer=run.err_layer,
            created_at=utcnow(),
        )

    @staticmethod
    def _apply(row: RunInstance, run: Run) -> None:
        row.status = run.status.value
        row.started_at = run.started_at
        row.ended_at = run.ended_at
        row.err_code = run.err_code
        row.err_layer = run.err_layer

    @staticmethod
    def _node_row(run: Run, node: NodeExecution) -> NodeExecutionRow:
        return NodeExecutionRow(
            run_id=run.run_id.value,
            node_id=node.node_id,
            status=node.status.value,
            channel=node.channel.value if node.channel else None,
            cost_ms=node.cost_ms,
            err_code=node.err_code,
            err_layer=node.err_layer,
            payload_digest=node.payload_digest,
        )

    @staticmethod
    def _to_domain(row: RunInstance, nodes: Sequence[NodeExecutionRow]) -> Run:
        from kernel.contexts.orchestration.domain.config_snapshot import ConfigSnapshot

        run = Run(
            run_id=RunId.parse(row.run_id),
            app_id=row.app_id,
            scene=row.scene,
            platform=row.platform,
            shop_id=row.shop_id,
            window=StatWindow(row.window_start, row.window_end),
            trigger_type=row.trigger_type,
            config_snapshot=ConfigSnapshot.build(row.config_snapshot or {}),
            gate_level_max=GateLevel.parse(row.gate_level_max),
            requested_by=row.requested_by,
            status=RunStatus(row.status),
            started_at=as_utc(row.started_at),
            ended_at=as_utc(row.ended_at),
            err_code=row.err_code,
            err_layer=row.err_layer,
        )
        run.nodes = [
            NodeExecution(
                node_id=node.node_id,
                status=NodeStatus(node.status),
                cost_ms=node.cost_ms,
                channel=Channel(node.channel) if node.channel else None,
                err_code=node.err_code,
                err_layer=node.err_layer,
                payload_digest=node.payload_digest,
            )
            for node in sorted(nodes, key=lambda n: n.node_id)
        ]
        return run


class SqlIdempotencyStore(IdempotencyStore):
    def __init__(self, database: Database) -> None:
        self.db = database

    def get(self, key: str) -> str | None:
        with self.db.session() as session:
            row = session.get(IdempotencyKeyRow, key)
            return row.run_id if row else None

    def claim(self, key: str, run_id: str) -> str | None:
        scope, _, value = key.partition(":")
        try:
            with self.db.session() as session:
                session.add(
                    IdempotencyKeyRow(key=key, scope=scope or "generic", value=value or key,
                                      run_id=run_id)
                )
            return None
        except IntegrityError:
            return self.get(key)


class OutboxPublisher(EventPublisher):
    """先落 outbox 再投递（至少一次）；M0 先同步写表，不接消息中间件。"""

    def __init__(self, database: Database) -> None:
        self.db = database

    def publish_all(self, events: list[DomainEvent]) -> None:
        if not events:
            return
        with self.db.session() as session:
            for event in events:
                session.add(
                    OutboxEvent(
                        event_id=event.event_id,
                        event_type=event.event_type,
                        aggregate_type="run" if event.aggregate_id.startswith("run_") else "unknown",
                        aggregate_id=event.aggregate_id or event.event_id,
                        payload=event.payload,
                        status="PENDING",
                        created_at=event.occurred_at,
                    )
                )

    def pending(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(OutboxEvent).where(OutboxEvent.status == "PENDING").limit(limit)
            ).scalars().all()
            return [
                {
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "aggregate_id": row.aggregate_id,
                    "payload": row.payload,
                }
                for row in rows
            ]
