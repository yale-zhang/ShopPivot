"""M2 L2 写入闸门闭环：计划 → 审批 → 一次性 token → 执行 → 回查 → 归档/补偿。"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from bootstrap.container import AppContainer
from kernel.contracts.extension_points import ActionResult


def _create_plan(client: TestClient, headers: dict[str, str], key: str, rows: list[dict[str, str]]):
    return client.post(
        "/api/v1/write-plans",
        json={
            "action_code": "S02.price_update",
            "platform": "demo",
            "shop_id": "SHOP-0001",
            "rows": rows,
            "idempotency_key": key,
        },
        headers=headers,
    )


def _price(container: AppContainer, sku: str) -> str:
    path = container.settings.storage_dir / "platform_state" / "demo_prices.json"
    return json.loads(path.read_text(encoding="utf-8"))[sku]


def test_l2_write_plan_approve_execute_verify_archive(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    created = _create_plan(
        m2_client, m2_headers, "m2-happy-1", [{"sku": "SKU-A", "after": "79.00"}]
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    plan = payload["plan"]
    assert plan["status"] == "PENDING_APPROVAL"
    assert plan["rows"][0]["before"] == "89.00"
    assert plan["rows"][0]["after"] == "79.00"

    detail = m2_client.get(f"/api/v1/change-orders/{payload['task_id']}", headers=m2_headers)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["can_approve"] is True
    assert detail_body["readonly"] is False
    assert detail_body["plan_id"] == plan["plan_id"]
    assert detail_body["evidence_complete"] is True

    approved = m2_client.post(
        f"/api/v1/write-plans/{plan['plan_id']}/approve",
        json={"reason": "活动价确认"},
        headers=m2_headers,
    )
    assert approved.status_code == 200, approved.text
    result = approved.json()
    assert result["plan"]["status"] == "VERIFIED"
    assert result["execution"]["status"] == "VERIFIED"
    assert result["execution"]["verify_result"]["verified"] is True
    assert _price(m2_seeded, "SKU-A") == "79.00"

    task = m2_seeded.approvals.get(payload["task_id"])
    assert task is not None and task.status.value == "ARCHIVED"
    assert task.evidence is not None and task.evidence.complete()
    assert task.evidence.after_shot

    after = m2_client.get(f"/api/v1/change-orders/{payload['task_id']}", headers=m2_headers).json()
    assert after["can_approve"] is False
    assert after["readonly"] is True
    assert after["execution"]["status"] == "VERIFIED"
    assert after["status"] == "ARCHIVED"

    replay = m2_client.post(
        f"/api/v1/write-plans/{plan['plan_id']}/approve",
        json={"reason": "重复批准"},
        headers=m2_headers,
    )
    assert replay.status_code == 403


def test_l2_reject_blocks_execution(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    created = _create_plan(
        m2_client, m2_headers, "m2-reject-1", [{"sku": "SKU-B", "after": "119.00"}]
    )
    plan = created.json()["plan"]
    rejected = m2_client.post(
        f"/api/v1/write-plans/{plan['plan_id']}/reject",
        json={"reason": "价格需重新核算"},
        headers=m2_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["plan"]["status"] == "REJECTED"
    assert _price(m2_seeded, "SKU-B") == "129.00"
    approve = m2_client.post(
        f"/api/v1/write-plans/{plan['plan_id']}/approve",
        json={},
        headers=m2_headers,
    )
    assert approve.status_code == 403


def test_m1_ceiling_denies_l2_plan(
    m1_client: TestClient, m1_headers: dict[str, str]
) -> None:
    denied = _create_plan(
        m1_client, m1_headers, "m2-on-l1", [{"sku": "SKU-A", "after": "79.00"}]
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "E007"


def test_l2_viewer_cannot_approve(
    m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    created = _create_plan(
        m2_client, m2_headers, "m2-viewer-1", [{"sku": "SKU-C", "after": "55.00"}]
    )
    plan = created.json()["plan"]
    token = m2_client.post(
        "/api/v1/auth/login", json={"username": "viewer", "password": "viewer123"}
    ).json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {token}"}
    approve = m2_client.post(
        f"/api/v1/write-plans/{plan['plan_id']}/approve", json={}, headers=viewer_headers
    )
    assert approve.status_code == 403
    assert approve.json()["code"] == "E003"


def test_write_token_is_single_use_and_bound(
    m2_seeded: AppContainer,
) -> None:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    m2_seeded.write_tokens.register(
        token="wt_test_token",
        task_id="task_a",
        plan_id="plan_a",
        expires_at=now + timedelta(minutes=5),
        issued_by="owner",
    )
    assert (
        m2_seeded.write_tokens.consume(
            token="wt_test_token", task_id="task_a", plan_id="plan_a", now=now
        )
        is True
    )
    assert (
        m2_seeded.write_tokens.consume(
            token="wt_test_token", task_id="task_a", plan_id="plan_a", now=now
        )
        is False
    )
    assert (
        m2_seeded.write_tokens.consume(
            token="wt_test_token", task_id="task_b", plan_id="plan_a", now=now
        )
        is False
    )


def test_verification_failure_compensates(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    handler = m2_seeded.write_handlers["S02.price_update"]

    def fake_apply(plan):  # type: ignore[no-untyped-def]
        # 模拟"页面写入了，但回查不一致"
        return ActionResult(
            verified=False,
            applied_rows=list(plan.rows),
            after_shot="shot://after/fail",
            details={"simulated": "verify_failure"},
        )

    handler.apply = fake_apply  # type: ignore[method-assign]
    created = _create_plan(
        m2_client, m2_headers, "m2-verify-fail-1", [{"sku": "SKU-D", "after": "189.00"}]
    )
    plan_id = created.json()["plan"]["plan_id"]
    approved = m2_client.post(
        f"/api/v1/write-plans/{plan_id}/approve", json={}, headers=m2_headers
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["plan"]["status"] == "COMPENSATED"
    assert body["execution"]["status"] == "FAILED"
    assert _price(m2_seeded, "SKU-D") == "199.00"


def test_price_drift_after_plan_blocks_execution(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    created = _create_plan(
        m2_client, m2_headers, "m2-drift-1", [{"sku": "SKU-E", "after": "35.00"}]
    )
    plan_id = created.json()["plan"]["plan_id"]
    state_path = Path(m2_seeded.settings.storage_dir) / "platform_state" / "demo_prices.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["SKU-E"] = "41.00"
    state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    approved = m2_client.post(
        f"/api/v1/write-plans/{plan_id}/approve", json={}, headers=m2_headers
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["plan"]["status"] == "FAILED"
    assert body["plan"]["error_code"] == "E006"
    # 未写入 → 不补偿，保留外部变更现场
    assert _price(m2_seeded, "SKU-E") == "41.00"


def test_write_plan_enforces_shop_scope(
    m2_client: TestClient, m2_editor_headers: dict[str, str]
) -> None:
    denied = m2_client.post(
        "/api/v1/write-plans",
        json={
            "action_code": "S02.price_update",
            "platform": "demo",
            "shop_id": "SHOP-OTHER",
            "rows": [{"sku": "SKU-A", "after": "79.00"}],
            "idempotency_key": "scope-denied",
        },
        headers=m2_editor_headers,
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "E003"


def test_legacy_demo_task_without_plan_is_not_approvable(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    from datetime import UTC, datetime, timedelta

    from kernel.contexts.approval.domain.approval_task import ApprovalTask
    from shared.gate_level import GateLevel
    from shared.run_id import RunId

    now = datetime.now(UTC)
    task = ApprovalTask.request(
        run_id=RunId.new(),
        gate_level=GateLevel.L2_MANUAL_APPROVAL,
        action_code="S02.price_update",
        write_plan={"rows": [], "created_at": now.isoformat()},
        sla_expires_at=now + timedelta(minutes=30),
        idempotency_key=f"legacy:{now.timestamp()}",
        scene="S02",
        platform="demo",
        shop_id="SHOP-0001",
    )
    m2_seeded.approvals.add(task)
    detail = m2_client.get(f"/api/v1/change-orders/{task.task_id}", headers=m2_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["can_approve"] is False
    assert body["readonly"] is True
    assert body["plan_id"] is None
