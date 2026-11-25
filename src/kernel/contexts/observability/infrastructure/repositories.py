"""审计与异常记录仓储（只增不改）。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from kernel.contexts.observability.domain.models import (
    AuditEntry,
    AuditPort,
    DeadLetterPort,
    ExceptionPort,
)
from kernel.persistence.base import Database, iso_or_none, utcnow
from kernel.persistence.tables import (
    AuditLogRow,
    DeadLetterRow,
    ExceptionRecordRow,
    N8nCommandLogRow,
)
from shared.errors.registry import DomainError


class SqlAuditRepository(AuditPort):
    def __init__(self, database: Database) -> None:
        self.db = database

    def record(self, entry: AuditEntry) -> None:
        with self.db.session() as session:
            session.add(
                AuditLogRow(
                    at=utcnow(),
                    actor=entry.actor,
                    action=entry.action,
                    object_type=entry.object_type,
                    object_id=entry.object_id,
                    reason=entry.reason,
                    before=entry.before,
                    after=entry.after,
                    ip=entry.ip,
                    result=entry.result,
                )
            )

    def recent(
        self,
        limit: int = 50,
        action: str | None = None,
        actor: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        since: Any = None,
        until: Any = None,
    ) -> list[dict[str, Any]]:
        with self.db.session() as session:
            statement = select(AuditLogRow).order_by(AuditLogRow.id.desc()).limit(limit)
            if action:
                statement = statement.where(AuditLogRow.action == action)
            if actor:
                statement = statement.where(AuditLogRow.actor == actor)
            if object_type:
                statement = statement.where(AuditLogRow.object_type == object_type)
            if object_id:
                statement = statement.where(AuditLogRow.object_id == object_id)
            if since is not None:
                statement = statement.where(AuditLogRow.at >= since)
            if until is not None:
                statement = statement.where(AuditLogRow.at <= until)
            rows = session.execute(statement).scalars().all()
            return [
                {
                    "id": row.id,
                    "at": iso_or_none(row.at),
                    "actor": row.actor,
                    "action": row.action,
                    "object_type": row.object_type,
                    "object_id": row.object_id,
                    "reason": row.reason,
                    "before": row.before,
                    "after": row.after,
                    "ip": row.ip,
                    "result": row.result,
                }
                for row in rows
            ]


class SqlExceptionRepository(ExceptionPort):
    def __init__(self, database: Database) -> None:
        self.db = database

    def record(
        self,
        error: DomainError,
        *,
        run_id: str | None = None,
        node_id: str | None = None,
        screenshot_ref: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        with self.db.session() as session:
            row = ExceptionRecordRow(
                run_id=run_id,
                node_id=node_id,
                err_code=error.code,
                err_layer=error.layer or error.spec.default_layer,
                message=error.message,
                retryable=error.retryable,
                status="OPEN",
                screenshot_ref=screenshot_ref,
                details=details or {},
                created_at=utcnow(),
            )
            session.add(row)
            session.flush()
            return int(row.id)

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(ExceptionRecordRow)
                .order_by(ExceptionRecordRow.id.desc())
                .limit(limit)
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "run_id": row.run_id,
                    "node_id": row.node_id,
                    "err_code": row.err_code,
                    "err_layer": row.err_layer,
                    "message": row.message,
                    "retryable": row.retryable,
                    "status": row.status,
                    "screenshot_ref": row.screenshot_ref,
                    "details": row.details,
                    "created_at": iso_or_none(row.created_at),
                }
                for row in rows
            ]


class SqlDeadLetterRepository(DeadLetterPort):
    def __init__(self, database: Database) -> None:
        self.db = database

    def record(
        self,
        error: DomainError,
        *,
        run_id: str,
        node_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        with self.db.session() as session:
            row = DeadLetterRow(
                run_id=run_id,
                node_id=node_id,
                err_code=error.code,
                err_layer=error.layer or error.spec.default_layer,
                message=error.message,
                payload=payload or {},
                attempts=1,
                status="OPEN",
                created_at=utcnow(),
            )
            session.add(row)
            session.flush()
            return int(row.id)

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(DeadLetterRow).order_by(DeadLetterRow.id.desc()).limit(limit)
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "run_id": row.run_id,
                    "node_id": row.node_id,
                    "err_code": row.err_code,
                    "err_layer": row.err_layer,
                    "message": row.message,
                    "payload": row.payload,
                    "attempts": row.attempts,
                    "status": row.status,
                    "created_at": iso_or_none(row.created_at),
                }
                for row in rows
            ]


class SqlN8nCommandLogRepository:
    """画布命令白名单审计：只记录放行/拒绝，不携带任何写凭据。"""

    def __init__(self, database: Database) -> None:
        self.db = database

    def record(
        self,
        *,
        command: str,
        token_scope: str,
        accepted: bool,
        detail: str = "",
        run_id: str | None = None,
    ) -> None:
        with self.db.session() as session:
            session.add(
                N8nCommandLogRow(
                    command=command,
                    token_scope=token_scope,
                    accepted=accepted,
                    detail=detail,
                    run_id=run_id,
                )
            )

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(N8nCommandLogRow).order_by(N8nCommandLogRow.id.desc()).limit(limit)
            ).scalars().all()
            return [
                {
                    "id": row.id,
                    "command": row.command,
                    "token_scope": row.token_scope,
                    "accepted": row.accepted,
                    "detail": row.detail,
                    "run_id": row.run_id,
                    "created_at": iso_or_none(row.created_at),
                }
                for row in rows
            ]
