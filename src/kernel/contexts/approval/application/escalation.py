"""审批 SLA 提醒与升级：临近超时提醒、极近升级、超时作废并通知。

幂等由 NotificationService 的 dedupe_key 保证（同一任务同一档只发一次）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kernel.contexts.approval.domain.approval_task import ApprovalTask
from kernel.contexts.approval.domain.ports import ApprovalTaskRepository
from kernel.contexts.integration.application.notification_service import NotificationService
from kernel.contexts.orchestration.domain.ports import Clock


@dataclass
class EscalationResult:
    reminded: list[str]
    escalated: list[str]
    expired: list[str]

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "reminded": self.reminded,
            "escalated": self.escalated,
            "expired": self.expired,
        }


class EscalateApprovalsUseCase:
    def __init__(
        self,
        repo: ApprovalTaskRepository,
        notifier: NotificationService,
        *,
        clock: Clock,
        reminder_minutes: int = 15,
        escalate_minutes: int = 5,
    ) -> None:
        self.repo = repo
        self.notifier = notifier
        self.clock = clock
        self.reminder_minutes = reminder_minutes
        self.escalate_minutes = escalate_minutes

    def __call__(self, now: datetime | None = None) -> EscalationResult:
        moment = now or self.clock.now()
        reminded: list[str] = []
        escalated: list[str] = []
        expired: list[str] = []
        for task in self.repo.pending(200):
            remaining = (task.sla_expires_at - moment).total_seconds() / 60
            if remaining <= 0:
                if task.expire(moment):
                    self.repo.save(task)
                    expired.append(task.task_id)
                    self._notify(
                        event="EVT-06",
                        task=task,
                        title=f"L2 待办已超时作废 · {task.action_code}",
                        body=(
                            f"{task.task_id} 超过 SLA 自动作废，未执行任何写入；"
                            "如需处理请重新发起变更单"
                        ),
                        bucket="expired",
                    )
                continue
            if remaining <= self.escalate_minutes:
                if self._notify(
                    event="EVT-05",
                    task=task,
                    title=f"L2 待办即将超时 · {task.action_code}",
                    body=f"{task.task_id} 剩余不足 {int(remaining)} 分钟，超时将自动作废",
                    bucket="escalation",
                ):
                    escalated.append(task.task_id)
            elif remaining <= self.reminder_minutes:
                if self._notify(
                    event="EVT-05",
                    task=task,
                    title=f"L2 待办提醒 · {task.action_code}",
                    body=f"{task.task_id} 剩余约 {int(remaining)} 分钟，请及时处理",
                    bucket="reminder",
                ):
                    reminded.append(task.task_id)
        return EscalationResult(reminded=reminded, escalated=escalated, expired=expired)

    def _notify(
        self, *, event: str, task: ApprovalTask, title: str, body: str, bucket: str
    ) -> bool:
        receiver = task.approver or "owner"
        return self.notifier.send(
            event=event,
            receiver=receiver,
            title=title,
            body=body,
            dedupe_key=f"{event}:{bucket}:{task.task_id}:{receiver}",
            payload={
                "task_id": task.task_id,
                "status": task.status.value,
                "action_code": task.action_code,
            },
        )
