"""M2 运营闭环：SLA 提醒/升级、审计筛选、审批历史、价格清单。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from bootstrap.container import AppContainer
from kernel.contexts.approval.application.escalation import EscalateApprovalsUseCase
from kernel.contexts.approval.domain.approval_task import ApprovalStatus, ApprovalTask
from shared.gate_level import GateLevel
from shared.run_id import RunId


def _task(container: AppContainer, minutes: int, suffix: str, approver: str = "editor") -> ApprovalTask:
    now = datetime.now(UTC)
    task = ApprovalTask.request(
        run_id=RunId.new(),
        gate_level=GateLevel.L2_MANUAL_APPROVAL,
        action_code="S02.price_update",
        write_plan={"rows": [{"target": "SKU-A", "before": "89.00", "after": "79.00"}]},
        sla_expires_at=now + timedelta(minutes=minutes),
        idempotency_key=f"escalation:{suffix}:{now.timestamp()}",
        scene="S02",
        platform="demo",
        shop_id="SHOP-0001",
        approver=approver,
    )
    container.approvals.add(task)
    return task


def test_escalation_reminds_escalates_and_expires_once(m2_seeded: AppContainer) -> None:
    reminded_task = _task(m2_seeded, 10, "remind")
    escalated_task = _task(m2_seeded, 2, "escalate")
    expired_task = _task(m2_seeded, -1, "expire")

    use_case = EscalateApprovalsUseCase(
        m2_seeded.approvals, m2_seeded.notifier, clock=m2_seeded.clock
    )
    first = use_case()
    assert reminded_task.task_id in first.reminded
    assert escalated_task.task_id in first.escalated
    assert expired_task.task_id in first.expired
    expired = m2_seeded.approvals.get(expired_task.task_id)
    assert expired is not None and expired.status is ApprovalStatus.EXPIRED

    notifications_after_first = len(m2_seeded.notification_log.recent(100))
    assert notifications_after_first >= 3

    second = use_case()
    assert second.reminded == [] and second.escalated == [] and second.expired == []
    assert len(m2_seeded.notification_log.recent(100)) == notifications_after_first


def test_audit_filters_and_approval_history(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    created = m2_client.post(
        "/api/v1/write-plans",
        json={
            "action_code": "S02.price_update",
            "platform": "demo",
            "shop_id": "SHOP-0001",
            "rows": [{"sku": "SKU-B", "after": "119.00"}],
            "idempotency_key": "ops-history-1",
        },
        headers=m2_headers,
    )
    plan = created.json()["plan"]
    m2_client.post(
        f"/api/v1/write-plans/{plan['plan_id']}/approve",
        json={"reason": "ok"},
        headers=m2_headers,
    )

    history = m2_client.get("/api/v1/approvals/history", headers=m2_headers).json()
    item = next(row for row in history["items"] if row["plan_id"] == plan["plan_id"])
    assert item["status"] == "ARCHIVED"
    assert item["execution_status"] == "VERIFIED"
    assert item["approver"] == "owner"

    audit = m2_client.get(
        "/api/v1/audit",
        params={"action": "write_plan.approve", "actor": "owner"},
        headers=m2_headers,
    ).json()
    assert audit["items"]
    assert all(row["action"] == "write_plan.approve" for row in audit["items"])

    by_object = m2_client.get(
        "/api/v1/audit", params={"object_id": plan["plan_id"]}, headers=m2_headers
    ).json()
    assert by_object["items"]


def test_platform_price_list(
    m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    payload = m2_client.get("/api/v1/platform/price-list", headers=m2_headers).json()
    assert payload["demo_only"] is True
    skus = {item["sku"] for item in payload["items"]}
    assert {"SKU-A", "SKU-B", "SKU-C"} <= skus
    assert all("price" in item for item in payload["items"])
