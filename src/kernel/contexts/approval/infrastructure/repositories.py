"""审批任务与变更单仓储。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update

import hashlib

from kernel.contexts.approval.domain.approval_task import ApprovalStatus, ApprovalTask
from kernel.contexts.approval.domain.ports import (
    ApprovalTaskRepository,
    ChangeOrderRepository,
    WriteExecutionRepository,
    WritePlanRepository,
    WriteTokenRepository,
)
from kernel.contexts.approval.domain.write_plan import (
    WriteExecution,
    WritePlan,
    WritePlanStatus,
)
from kernel.persistence.base import Database, as_utc, iso_or_none, utcnow
from kernel.persistence.tables import (
    ApprovalEvidenceRow,
    ApprovalTaskRow,
    ChangeOrderRow,
    WriteExecutionRow,
    WritePlanRow,
    WriteTokenRow,
)
from shared.evidence import EvidenceSet
from shared.gate_level import GateLevel
from shared.run_id import RunId


class SqlApprovalTaskRepository(ApprovalTaskRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def add(self, task: ApprovalTask) -> None:
        with self.db.session() as session:
            session.add(self._to_row(task))
            if task.evidence:
                session.add(self._evidence_row(task))
            self._add_change_order(session, task)

    def save(self, task: ApprovalTask) -> None:
        with self.db.session() as session:
            row = session.get(ApprovalTaskRow, task.task_id)
            if row is None:
                session.add(self._to_row(task))
            else:
                row.status = task.status.value
                row.change_order_no = task.change_order_no
                row.approver = task.approver
                row.sla_expires_at = task.sla_expires_at
                row.reason = task.reason
            evidence = session.get(ApprovalEvidenceRow, task.task_id)
            if task.evidence and evidence is None:
                session.add(self._evidence_row(task))
            elif task.evidence and evidence is not None:
                evidence.operator = task.evidence.operator
                evidence.decided_at = task.evidence.decided_at
                evidence.change_order_no = task.evidence.change_order_no
                evidence.before_shot = task.evidence.before_shot
                evidence.after_shot = task.evidence.after_shot
            self._add_change_order(session, task)

    def get(self, task_id: str) -> ApprovalTask | None:
        with self.db.session() as session:
            row = session.get(ApprovalTaskRow, task_id)
            if row is None:
                return None
            evidence = session.get(ApprovalEvidenceRow, task_id)
            return self._to_domain(row, evidence)

    def find_by_idempotency(self, key: str) -> ApprovalTask | None:
        with self.db.session() as session:
            row = session.execute(
                select(ApprovalTaskRow).where(ApprovalTaskRow.idempotency_key == key)
            ).scalar_one_or_none()
            if row is None:
                return None
            evidence = session.get(ApprovalEvidenceRow, row.task_id)
            return self._to_domain(row, evidence)

    def by_run(self, run_id: RunId) -> list[ApprovalTask]:
        with self.db.session() as session:
            rows = session.execute(
                select(ApprovalTaskRow)
                .where(ApprovalTaskRow.run_id == run_id.value)
                .order_by(ApprovalTaskRow.created_at)
            ).scalars().all()
            return [
                self._to_domain(row, session.get(ApprovalEvidenceRow, row.task_id))
                for row in rows
            ]

    def recent(self, limit: int = 50) -> list[ApprovalTask]:
        with self.db.session() as session:
            rows = session.execute(
                select(ApprovalTaskRow)
                .order_by(ApprovalTaskRow.created_at.desc())
                .limit(limit)
            ).scalars().all()
            return [
                self._to_domain(row, session.get(ApprovalEvidenceRow, row.task_id))
                for row in rows
            ]

    def pending(self, limit: int = 50) -> list[ApprovalTask]:
        with self.db.session() as session:
            rows = session.execute(
                select(ApprovalTaskRow)
                .where(ApprovalTaskRow.status == ApprovalStatus.PENDING.value)
                .order_by(ApprovalTaskRow.sla_expires_at)
                .limit(limit)
            ).scalars().all()
            return [
                self._to_domain(row, session.get(ApprovalEvidenceRow, row.task_id))
                for row in rows
            ]

    def overdue(self, now: datetime, limit: int = 100) -> list[ApprovalTask]:
        with self.db.session() as session:
            rows = session.execute(
                select(ApprovalTaskRow)
                .where(
                    ApprovalTaskRow.status == ApprovalStatus.PENDING.value,
                    ApprovalTaskRow.sla_expires_at <= now,
                )
                .limit(limit)
            ).scalars().all()
            return [
                self._to_domain(row, session.get(ApprovalEvidenceRow, row.task_id))
                for row in rows
            ]

    # ------------------------------------------------------------------ mapping
    @staticmethod
    def _to_row(task: ApprovalTask) -> ApprovalTaskRow:
        return ApprovalTaskRow(
            task_id=task.task_id,
            run_id=task.run_id.value,
            gate_level=task.gate_level.value,
            action_code=task.action_code,
            scene=task.scene,
            platform=task.platform,
            shop_id=task.shop_id,
            write_plan=task.write_plan,
            write_plan_hash=task.write_plan_hash,
            impact_scope=task.impact_scope,
            status=task.status.value,
            sla_expires_at=task.sla_expires_at,
            change_order_no=task.change_order_no,
            requested_by=task.requested_by,
            approver=task.approver,
            reason=task.reason,
            idempotency_key=task.idempotency_key,
        )

    @staticmethod
    def _evidence_row(task: ApprovalTask) -> ApprovalEvidenceRow:
        assert task.evidence is not None
        return ApprovalEvidenceRow(
            task_id=task.task_id,
            operator=task.evidence.operator,
            decided_at=task.evidence.decided_at,
            change_order_no=task.evidence.change_order_no,
            before_shot=task.evidence.before_shot,
            after_shot=task.evidence.after_shot,
        )

    @staticmethod
    def _add_change_order(session: Any, task: ApprovalTask) -> None:
        if not task.change_order_no:
            return
        row = session.get(ChangeOrderRow, task.change_order_no)
        if row is None:
            session.add(
                ChangeOrderRow(
                    change_order_no=task.change_order_no,
                    task_id=task.task_id,
                    status="APPROVED",
                    before_snapshot={},
                    after_snapshot=task.write_plan,
                    rollback_plan="按变更单预置还原步骤执行（M2 启用）",
                )
            )

    @staticmethod
    def _to_domain(
        row: ApprovalTaskRow, evidence_row: ApprovalEvidenceRow | None
    ) -> ApprovalTask:
        sla = as_utc(row.sla_expires_at)
        if sla is None:
            raise ValueError(f"审批任务 {row.task_id} 缺少 SLA")
        task = ApprovalTask(
            task_id=row.task_id,
            run_id=RunId.parse(row.run_id),
            gate_level=GateLevel.parse(row.gate_level),
            action_code=row.action_code,
            write_plan=row.write_plan or {},
            write_plan_hash=row.write_plan_hash,
            sla_expires_at=sla,
            idempotency_key=row.idempotency_key,
            scene=row.scene,
            platform=row.platform,
            shop_id=row.shop_id,
            impact_scope=row.impact_scope,
            status=ApprovalStatus(row.status),
            change_order_no=row.change_order_no,
            requested_by=row.requested_by,
            approver=row.approver,
            reason=row.reason,
        )
        if evidence_row:
            decided_at = as_utc(evidence_row.decided_at)
            if decided_at is None:
                raise ValueError(f"审批证据 {evidence_row.task_id} 缺少确认时间")
            task.evidence = EvidenceSet(
                operator=evidence_row.operator,
                decided_at=decided_at,
                change_order_no=evidence_row.change_order_no,
                before_shot=evidence_row.before_shot,
                after_shot=evidence_row.after_shot,
            )
        return task


class SqlChangeOrderRepository(ChangeOrderRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def get(self, change_order_no: str) -> dict[str, Any] | None:
        with self.db.session() as session:
            row = session.get(ChangeOrderRow, change_order_no)
            return self._dict(row) if row else None

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(ChangeOrderRow).order_by(ChangeOrderRow.created_at.desc()).limit(limit)
            ).scalars().all()
            return [self._dict(row) for row in rows]

    @staticmethod
    def _dict(row: ChangeOrderRow) -> dict[str, Any]:
        return {
            "change_order_no": row.change_order_no,
            "task_id": row.task_id,
            "status": row.status,
            "before_snapshot": row.before_snapshot,
            "after_snapshot": row.after_snapshot,
            "rollback_plan": row.rollback_plan,
            "evidence_ref": row.evidence_ref,
            "created_at": iso_or_none(row.created_at),
        }


class SqlWritePlanRepository(WritePlanRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def add(self, plan: WritePlan) -> None:
        with self.db.session() as session:
            session.add(self._to_row(plan))

    def save(self, plan: WritePlan) -> None:
        with self.db.session() as session:
            row = session.get(WritePlanRow, plan.plan_id)
            if row is None:
                session.add(self._to_row(plan))
                return
            row.status = plan.status.value
            row.approval_task_id = plan.approval_task_id
            row.execution_id = plan.execution_id
            row.error_code = plan.error_code
            row.error_layer = plan.error_layer
            row.updated_at = utcnow()

    def get(self, plan_id: str) -> WritePlan | None:
        with self.db.session() as session:
            row = session.get(WritePlanRow, plan_id)
            return self._to_domain(row) if row else None

    def find_by_idempotency(self, key: str) -> WritePlan | None:
        with self.db.session() as session:
            row = session.execute(
                select(WritePlanRow).where(WritePlanRow.idempotency_key == key)
            ).scalar_one_or_none()
            return self._to_domain(row) if row else None

    def recent(self, limit: int = 50) -> list[WritePlan]:
        with self.db.session() as session:
            rows = session.execute(
                select(WritePlanRow).order_by(WritePlanRow.created_at.desc()).limit(limit)
            ).scalars().all()
            return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_row(plan: WritePlan) -> WritePlanRow:
        return WritePlanRow(
            plan_id=plan.plan_id,
            action_code=plan.action_code,
            scene=plan.scene,
            platform=plan.platform,
            shop_id=plan.shop_id,
            status=plan.status.value,
            rows=plan.rows,
            before_snapshot=plan.before_snapshot,
            summary=plan.summary,
            impact_scope=plan.impact_scope,
            rollback_plan=plan.rollback_plan,
            evidence=plan.evidence,
            plan_hash=plan.plan_hash,
            requested_by=plan.requested_by,
            approval_task_id=plan.approval_task_id,
            execution_id=plan.execution_id,
            idempotency_key=plan.idempotency_key,
            error_code=plan.error_code,
            error_layer=plan.error_layer,
            created_at=plan.created_at or utcnow(),
        )

    @staticmethod
    def _to_domain(row: WritePlanRow) -> WritePlan:
        return WritePlan(
            plan_id=row.plan_id,
            action_code=row.action_code,
            scene=row.scene,
            platform=row.platform,
            shop_id=row.shop_id,
            rows=list(row.rows or []),
            before_snapshot=dict(row.before_snapshot or {}),
            summary=row.summary,
            impact_scope=row.impact_scope,
            rollback_plan=row.rollback_plan,
            evidence=list(row.evidence or []),
            plan_hash=row.plan_hash,
            idempotency_key=row.idempotency_key,
            requested_by=row.requested_by,
            status=WritePlanStatus(row.status),
            approval_task_id=row.approval_task_id,
            execution_id=row.execution_id,
            error_code=row.error_code,
            error_layer=row.error_layer,
            created_at=as_utc(row.created_at),
        )


class SqlWriteExecutionRepository(WriteExecutionRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def add(self, execution: WriteExecution) -> None:
        with self.db.session() as session:
            session.add(self._to_row(execution))

    def save(self, execution: WriteExecution) -> None:
        with self.db.session() as session:
            row = session.get(WriteExecutionRow, execution.execution_id)
            if row is None:
                session.add(self._to_row(execution))
                return
            row.status = execution.status
            row.applied_rows = execution.applied_rows
            row.before_shot = execution.before_shot
            row.after_shot = execution.after_shot
            row.verify_result = execution.verify_result
            row.details = execution.details
            row.err_code = execution.err_code
            row.err_layer = execution.err_layer
            row.ended_at = execution.ended_at

    def by_plan(self, plan_id: str) -> list[WriteExecution]:
        with self.db.session() as session:
            rows = session.execute(
                select(WriteExecutionRow)
                .where(WriteExecutionRow.plan_id == plan_id)
                .order_by(WriteExecutionRow.started_at)
            ).scalars().all()
            return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_row(execution: WriteExecution) -> WriteExecutionRow:
        return WriteExecutionRow(
            execution_id=execution.execution_id,
            plan_id=execution.plan_id,
            task_id=execution.task_id,
            status=execution.status,
            applied_rows=execution.applied_rows,
            before_shot=execution.before_shot,
            after_shot=execution.after_shot,
            verify_result=execution.verify_result,
            details=execution.details,
            err_code=execution.err_code,
            err_layer=execution.err_layer,
            started_at=execution.started_at or utcnow(),
            ended_at=execution.ended_at,
        )

    @staticmethod
    def _to_domain(row: WriteExecutionRow) -> WriteExecution:
        return WriteExecution(
            execution_id=row.execution_id,
            plan_id=row.plan_id,
            task_id=row.task_id,
            status=row.status,
            applied_rows=list(row.applied_rows or []),
            before_shot=row.before_shot,
            after_shot=row.after_shot,
            verify_result=dict(row.verify_result or {}),
            details=dict(row.details or {}),
            err_code=row.err_code,
            err_layer=row.err_layer,
            started_at=as_utc(row.started_at),
            ended_at=as_utc(row.ended_at),
        )


class SqlWriteTokenRepository(WriteTokenRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def register(
        self,
        *,
        token: str,
        task_id: str,
        plan_id: str,
        expires_at: datetime,
        issued_by: str,
    ) -> None:
        with self.db.session() as session:
            session.add(
                WriteTokenRow(
                    token_hash=self._hash(token),
                    task_id=task_id,
                    plan_id=plan_id,
                    issued_by=issued_by,
                    expires_at=expires_at,
                )
            )

    def consume(self, *, token: str, task_id: str, plan_id: str, now: datetime) -> bool:
        with self.db.session() as session:
            result = session.execute(
                update(WriteTokenRow)
                .where(
                    WriteTokenRow.token_hash == self._hash(token),
                    WriteTokenRow.task_id == task_id,
                    WriteTokenRow.plan_id == plan_id,
                    WriteTokenRow.consumed_at.is_(None),
                    WriteTokenRow.expires_at >= now,
                )
                .values(consumed_at=now)
            )
            return bool(result.rowcount)
