"""M2 第二批动作：S03 活动提报、审批转交、S04 投放归集与预警。"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from bootstrap.container import AppContainer, run_scene


def _create_campaign_plan(client: TestClient, headers: dict[str, str], key: str, price: str = "69.00"):
    return client.post(
        "/api/v1/write-plans",
        json={
            "action_code": "S03.campaign_apply",
            "platform": "demo",
            "shop_id": "SHOP-0001",
            "rows": [{"campaign_id": "C-618", "sku": "SKU-A", "activity_price": price}],
            "idempotency_key": key,
        },
        headers=headers,
    )


def test_s03_campaign_apply_full_chain_and_duplicate_block(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    created = _create_campaign_plan(m2_client, m2_headers, "s03-chain")
    assert created.status_code == 200, created.text
    plan = created.json()["plan"]
    assert plan["status"] == "PENDING_APPROVAL"
    assert plan["rows"][0]["before"] == "未提报"
    assert plan["rows"][0]["after"] == "69.00"

    approved = m2_client.post(
        f"/api/v1/write-plans/{plan['plan_id']}/approve", json={"reason": "报名 618"}, headers=m2_headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["plan"]["status"] == "VERIFIED"
    signup_path = m2_seeded.settings.storage_dir / "platform_state" / "campaign_signups.json"
    signups = json.loads(signup_path.read_text(encoding="utf-8"))
    assert signups["C-618:SKU-A"] == "69.00"

    duplicate = _create_campaign_plan(m2_client, m2_headers, "s03-duplicate")
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "E006"
    assert "重复" in duplicate.json()["message"]


def test_s03_rejects_activity_price_above_daily_price(
    m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    denied = _create_campaign_plan(m2_client, m2_headers, "s03-high-price", price="199.00")
    assert denied.status_code == 409
    assert denied.json()["code"] == "E006"
    assert "高于日常价" in denied.json()["message"]


def test_transfer_resets_approver_and_sla(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    created = _create_campaign_plan(m2_client, m2_headers, "transfer-1")
    task_id = created.json()["task_id"]
    before = m2_client.get(f"/api/v1/change-orders/{task_id}", headers=m2_headers).json()
    assert before["header"]["approver"] == "owner"

    transferred = m2_client.post(
        f"/api/v1/change-orders/{task_id}/transfer",
        json={"approver": "editor", "reason": "主管转交"},
        headers=m2_headers,
    )
    assert transferred.status_code == 200, transferred.text
    body = transferred.json()
    assert body["approver"] == "editor"
    assert body["status"] == "PENDING"
    after = m2_client.get(f"/api/v1/change-orders/{task_id}", headers=m2_headers).json()
    assert after["header"]["approver"] == "editor"
    assert after["header"]["sla_expires_at"] != before["header"]["sla_expires_at"]
    assert any(
        item["action"] == "approval.transfer" for item in m2_seeded.audit.recent(20)
    )


def test_s04_ads_monitor_and_alert_summary(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    result = run_scene(m2_seeded, "S04", day="2026-11-25")
    assert result.run.status.value == "SUCCEEDED", result.run.err_code
    assert result.scene_result is not None
    assert result.scene_result.details["campaigns"] == 2
    assert result.scene_result.details["alerts"] == 1

    summary = m2_client.get("/api/v1/ads/summary", headers=m2_headers).json()
    assert summary["run_id"] == result.run.run_id.value
    assert summary["counts"] == {"ALERT": 1, "OK": 1}
    assert summary["totals"]["cost"] == 400.0
    assert summary["totals"]["roi"] == 3.12
    alert = next(row for row in summary["campaigns"] if row["alert_level"] == "ALERT")
    assert alert["campaign"] == "场景推广"
    assert "不自动调价" in summary["note"]
    assert "不自动调价" in alert["suggestion"]

    empty = m2_client.get("/api/v1/ads/summary?run_id=run_0123456789abcdef", headers=m2_headers)
    assert empty.status_code == 404
