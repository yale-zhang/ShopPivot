"""ApprovalTask 状态机单测（表3-9/3-10/8-4）。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kernel.contexts.approval.domain.approval_task import ApprovalStatus, ApprovalTask
from shared.errors.registry import DomainError
from shared.evidence import EvidenceSet
from shared.gate_level import GateLevel
from shared.run_id import RunId


def _task(sla_minutes: int = 30) -> ApprovalTask:
    now = datetime.now(UTC)
    return ApprovalTask.request(
        run_id=RunId.new(),
        gate_level=GateLevel.L2_MANUAL_APPROVAL,
        action_code="S02.price_update",
        write_plan={"rows": [{"target": "SKU-A", "before": "89", "after": "79"}]},
        sla_expires_at=now + timedelta(minutes=sla_minutes),
        idempotency_key=f"test:{now.timestamp()}",
        scene="S02",
        platform="demo",
        shop_id="SHOP-0001",
    )


def _evidence() -> EvidenceSet:
    return EvidenceSet(
        operator="owner",
        decided_at=datetime.now(UTC),
        change_order_no="CO-2026-001",
        before_shot="shot://before",
        after_shot="shot://after",
    )


def test_only_l2_creates_task() -> None:
    with pytest.raises(DomainError):
        ApprovalTask.request(
            run_id=RunId.new(),
            gate_level=GateLevel.L0_READ_ONLY,
            action_code="S01.report",
            write_plan={},
            sla_expires_at=datetime.now(UTC),
            idempotency_key="x",
        )


def test_grant_requires_complete_evidence() -> None:
    task = _task()
    partial = EvidenceSet("owner", datetime.now(UTC), "", "before", "after")
    with pytest.raises(DomainError) as exc:
        task.grant(partial, datetime.now(UTC))
    assert exc.value.code == "E007"
    assert task.status is ApprovalStatus.PENDING


def test_grant_after_sla_expires_and_never_executes() -> None:
    task = _task(sla_minutes=0)
    later = datetime.now(UTC) + timedelta(minutes=5)
    with pytest.raises(DomainError) as exc:
        task.grant(_evidence(), later)
    assert exc.value.code == "E007"
    assert task.status is ApprovalStatus.EXPIRED
    assert task.change_order_no is None


def test_grant_issues_token_bound_to_task() -> None:
    task = _task()
    now = datetime.now(UTC)
    token = task.grant(_evidence(), now)
    assert task.status is ApprovalStatus.APPROVED
    assert token.task_id == task.task_id
    assert token.is_valid(task.task_id, now)
    assert not token.is_valid("task_other", now)
    assert not token.is_valid(task.task_id, now + timedelta(minutes=10))


def test_reject_requires_reason_and_blocks_auto_retry() -> None:
    task = _task()
    with pytest.raises(DomainError):
        task.reject("  ", datetime.now(UTC))
    task.reject("价格需重新核算", datetime.now(UTC))
    assert task.status is ApprovalStatus.REJECTED
    with pytest.raises(DomainError):
        task.grant(_evidence(), datetime.now(UTC))


def test_expire_only_after_sla() -> None:
    task = _task(sla_minutes=10)
    now = datetime.now(UTC)
    assert task.expire(now) is False
    assert task.expire(now + timedelta(minutes=11)) is True
    assert task.status is ApprovalStatus.EXPIRED


def test_verify_failure_sets_status_and_raises() -> None:
    task = _task()
    task.grant(_evidence(), datetime.now(UTC))
    task.mark_executing()
    with pytest.raises(DomainError):
        task.verify(consistent=False, note="平台回查不一致")
    assert task.status is ApprovalStatus.VERIFY_FAILED
    with pytest.raises(DomainError):
        task.archive()


def test_archive_requires_verified_and_evidence() -> None:
    task = _task()
    with pytest.raises(DomainError):
        task.archive()
    task.grant(_evidence(), datetime.now(UTC))
    task.mark_executing()
    task.verify(consistent=True)
    task.archive()
    assert task.status is ApprovalStatus.ARCHIVED


def test_approval_allows_missing_after_shot_until_archive() -> None:
    task = _task()
    now = datetime.now(UTC)
    evidence = EvidenceSet(
        operator="owner",
        decided_at=now,
        change_order_no="CO-1",
        before_shot="shot://before",
        after_shot="",
    )
    assert evidence.approvable()
    assert not evidence.complete()
    token = task.grant(evidence, now)
    assert token.task_id == task.task_id
    task.mark_executing()
    task.attach_after_shot("shot://after")
    task.verify(consistent=True)
    task.archive()
    assert task.status is ApprovalStatus.ARCHIVED
    assert task.evidence is not None and task.evidence.complete()
