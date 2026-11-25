"""Worker 心跳与能力仓储。"""
from __future__ import annotations

from sqlalchemy import select

from kernel.contexts.execution.domain.worker import Worker, WorkerKind, WorkerRepository, WorkerStatus
from kernel.persistence.base import Database, as_utc, utcnow
from kernel.persistence.tables import WorkerHeartbeatRow, WorkerRow


class SqlWorkerRepository(WorkerRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def upsert(self, worker: Worker) -> None:
        with self.db.session() as session:
            row = session.get(WorkerRow, worker.worker_id)
            if row is None:
                row = WorkerRow(
                    worker_id=worker.worker_id,
                    kind=worker.kind.value,
                    status=worker.status.value,
                    capabilities=worker.capabilities,
                    queue_depth=worker.queue_depth,
                    last_heartbeat_at=utcnow(),
                )
                session.add(row)
            else:
                row.status = worker.status.value
                row.capabilities = worker.capabilities
                row.queue_depth = worker.queue_depth
                row.last_heartbeat_at = utcnow()
            session.add(
                WorkerHeartbeatRow(
                    worker_id=worker.worker_id,
                    status=worker.status.value,
                    queue_depth=worker.queue_depth,
                    at=utcnow(),
                )
            )

    def get(self, worker_id: str) -> Worker | None:
        with self.db.session() as session:
            row = session.get(WorkerRow, worker_id)
            return self._to_domain(row) if row else None

    def list(self) -> list[Worker]:
        with self.db.session() as session:
            rows = session.execute(select(WorkerRow)).scalars().all()
            return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: WorkerRow) -> Worker:
        return Worker(
            worker_id=row.worker_id,
            kind=WorkerKind(row.kind),
            status=WorkerStatus(row.status),
            capabilities=list(row.capabilities or []),
            queue_depth=row.queue_depth,
            last_heartbeat_at=as_utc(row.last_heartbeat_at),
        )
