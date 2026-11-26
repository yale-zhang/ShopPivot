"""P13 1688 选品与采购：mock 提供方全链、风险阻断、L2 闸门与 HITL 边界。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from bootstrap.container import AppContainer
from shared.errors.registry import DomainError


def _search(container: AppContainer, keyword: str = "垃圾袋"):
    from bootstrap.container import run_scene

    return run_scene(container, "S10", params={"keyword": keyword, "limit": 10})


def test_s10_sourcing_scores_and_flags_risk(m2_seeded: AppContainer) -> None:
    result = _search(m2_seeded)
    assert result.run.status.value == "SUCCEEDED", result.run.err_code
    candidates = m2_seeded.sourcing.by_run(result.run.run_id)
    assert [item["offer_id"] for item in candidates][0] == "1688-1001"
    assert candidates[0]["score"] > candidates[-1]["score"]
    by_id = {item["offer_id"]: item for item in candidates}
    assert "品牌未授权" in by_id["1688-1003"]["risk_flags"]
    assert "无近30天分销单" in by_id["1688-1004"]["risk_flags"]
    assert "需邮费" in by_id["1688-1002"]["risk_flags"]


def test_purchase_plan_rejects_brand_and_moq(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    _search(m2_seeded)
    brand = m2_client.post(
        "/api/v1/write-plans",
        json={
            "action_code": "S11.purchase_order",
            "platform": "demo",
            "shop_id": "SHOP-0001",
            "rows": [{"offer_id": "1688-1003", "quantity": 60}],
            "idempotency_key": "s11-brand",
        },
        headers=m2_headers,
    )
    assert brand.status_code == 409
    assert brand.json()["code"] == "E006"
    assert "品牌未授权" in brand.json()["message"]

    moq = m2_client.post(
        "/api/v1/write-plans",
        json={
            "action_code": "S11.purchase_order",
            "platform": "demo",
            "shop_id": "SHOP-0001",
            "rows": [{"offer_id": "1688-1002", "quantity": 1}],
            "idempotency_key": "s11-moq",
        },
        headers=m2_headers,
    )
    assert moq.status_code == 409
    assert "起订量" in moq.json()["message"]


def test_purchase_creates_checkout_but_never_pays(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    _search(m2_seeded)
    created = m2_client.post(
        "/api/v1/write-plans",
        json={
            "action_code": "S11.purchase_order",
            "platform": "demo",
            "shop_id": "SHOP-0001",
            "rows": [{"offer_id": "1688-1001", "quantity": 10}],
            "idempotency_key": "s11-happy",
        },
        headers=m2_headers,
    )
    assert created.status_code == 200, created.text
    plan = created.json()["plan"]
    assert plan["status"] == "PENDING_APPROVAL"
    approved = m2_client.post(
        f"/api/v1/write-plans/{plan['plan_id']}/approve",
        json={"reason": "首单试采"},
        headers=m2_headers,
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["plan"]["status"] == "VERIFIED"
    assert body["execution"]["status"] == "VERIFIED"
    order = m2_seeded.purchases.get(plan["plan_id"])
    assert order is not None
    assert order.status.value == "AWAITING_PAYMENT"
    assert order.checkout_id.startswith("mockco_")
    assert "ucp-b2b.com" in order.continue_url
    assert order.total == 85.00
    skill_runs = [
        run
        for run in m2_seeded.skill_runs.recent(50)
        if run.scene == "S11" and run.capability == "purchase.checkout"
    ]
    assert skill_runs and skill_runs[0].status == "SUCCEEDED"

    purchases = m2_client.get("/api/v1/purchases", headers=m2_headers).json()
    assert purchases["items"][0]["status"] == "AWAITING_PAYMENT"
    assert purchases["items"][0]["task_id"]
    refreshed = m2_client.post(
        f"/api/v1/purchases/{plan['plan_id']}/refresh", headers=m2_headers
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "AWAITING_PAYMENT"


def test_sourcing_api_and_provider_status(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    response = m2_client.post(
        "/api/v1/sourcing/search",
        json={"keyword": "垃圾袋", "limit": 5},
        headers=m2_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "SUCCEEDED"
    assert body["count"] >= 3
    assert body["provider"] == "mock-1688"

    candidates = m2_client.get("/api/v1/sourcing/candidates", headers=m2_headers).json()
    assert candidates["count"] == body["count"]
    first = candidates["candidates"][0]
    detail = m2_client.get(
        f"/api/v1/sourcing/candidates/{first['offer_id']}", headers=m2_headers
    )
    assert detail.status_code == 200
    assert detail.json()["offer_id"] == first["offer_id"]

    provider = m2_client.get("/api/v1/sourcing/provider", headers=m2_headers).json()
    assert provider["mode"] == "mock"
    assert "不代" in provider["note"] or "支付" in provider["note"]


def test_l2_purchase_denied_under_l1(m1_seeded: AppContainer) -> None:
    from kernel.contexts.approval.application.write_flow import CreateWritePlanCommand

    with_error = None
    try:
        m1_seeded.write_flow.create_plan(
            CreateWritePlanCommand(
                action_code="S11.purchase_order",
                platform="demo",
                shop_id="SHOP-0001",
                rows=[{"offer_id": "1688-1001", "quantity": 5}],
                requested_by="owner",
                idempotency_key="l1-purchase",
            )
        )
    except DomainError as exc:
        with_error = exc
    assert with_error is not None
    assert with_error.code == "E007"
    assert "L1" in with_error.message or "上限" in with_error.message
