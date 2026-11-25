"""审批治理端口。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from kernel.contexts.approval.domain.approval_task import ApprovalTask
from kernel.contexts.approval.domain.write_plan import WriteExecution, WritePlan
from shared.run_id import RunId


class ApprovalTaskRepository(Protocol):
    def add(self, task: ApprovalTask) -> None: ...

    def save(self, task: ApprovalTask) -> None: ...

    def get(self, task_id: str) -> ApprovalTask | None: ...

    def find_by_idempotency(self, key: str) -> ApprovalTask | None: ...

    def by_run(self, run_id: RunId) -> list[ApprovalTask]: ...

    def pending(self, limit: int = 50) -> list[ApprovalTask]: ...

    def recent(self, limit: int = 50) -> list[ApprovalTask]: ...

    def overdue(self, now: datetime, limit: int = 100) -> list[ApprovalTask]: ...


class WritePlanRepository(Protocol):
    def add(self, plan: WritePlan) -> None: ...

    def save(self, plan: WritePlan) -> None: ...

    def get(self, plan_id: str) -> WritePlan | None: ...

    def find_by_idempotency(self, key: str) -> WritePlan | None: ...

    def recent(self, limit: int = 50) -> list[WritePlan]: ...


class WriteExecutionRepository(Protocol):
    def add(self, execution: WriteExecution) -> None: ...

    def save(self, execution: WriteExecution) -> None: ...

    def by_plan(self, plan_id: str) -> list[WriteExecution]: ...


class WriteTokenRepository(Protocol):
    def register(
        self,
        *,
        token: str,
        task_id: str,
        plan_id: str,
        expires_at: datetime,
        issued_by: str,
    ) -> None: ...

    def consume(self, *, token: str, task_id: str, plan_id: str, now: datetime) -> bool: ...


class ChangeOrderRepository(Protocol):
    def get(self, change_order_no: str) -> dict[str, Any] | None: ...

    def recent(self, limit: int = 20) -> list[dict[str, Any]]: ...
