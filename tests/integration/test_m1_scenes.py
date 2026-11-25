"""M1 场景验收：S05 评价巡检、S07 库存对账、发布自检、订阅、n8n 命令白名单。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from bootstrap.container import AppContainer, run_scene


def test_s05_creates_deduped_review_ticket(m1_seeded: AppContainer) -> None:
    result = run_scene(m1_seeded, "S05", day="2026-11-25")
    assert result.run.status.value == "SUCCEEDED"
    assert result.scene_result is not None
    assert result.scene_result.details["tickets_created"] == 1

    tickets = m1_seeded.review_tickets.list()
    assert len(tickets) == 1
    ticket = tickets[0]
    assert ticket["review_id"] == "RV-002"
    assert ticket["severity"] == "MEDIUM"
    assert ticket["status"] == "OPEN"
    assert "13987654321" not in ticket["content_masked"]
    assert ticket["content_masked"] != ""

    # 再跑同一天：幂等键命中，不产生第二条工单
    again = run_scene(m1_seeded, "S05", day="2026-11-25")
    assert again.deduplicated is True
    assert len(m1_seeded.review_tickets.list()) == 1


def test_s05_assign_and_close_ticket(
    m1_seeded: AppContainer, m1_client: TestClient, m1_headers: dict[str, str]
) -> None:
    run_scene(m1_seeded, "S05", day="2026-11-25")
    ticket = m1_seeded.review_tickets.list()[0]
    assigned = m1_client.post(
        f"/api/v1/reviews/tickets/{ticket['ticket_id']}/assign",
        json={"assignee": "客服小张"},
        headers=m1_headers,
    )
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "ASSIGNED"
    closed = m1_client.post(
        f"/api/v1/reviews/tickets/{ticket['ticket_id']}/close",
        json={"resolution": "已补发并致歉"},
        headers=m1_headers,
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"
    todos = m1_client.get("/api/v1/todos", headers=m1_headers).json()
    assert "TODO-REVIEW" not in todos["counts"]


def test_s07_reconciles_three_way_inventory(m1_seeded: AppContainer) -> None:
    result = run_scene(m1_seeded, "S07", day="2026-11-25")
    assert result.run.status.value == "SUCCEEDED"
    assert result.scene_result is not None
    details = result.scene_result.details
    assert details["diffs"] == 5
    assert details["counts"] == {
        "MISMATCH": 1,
        "STOCKOUT": 1,
        "CONSISTENT": 1,
        "OVERSELL": 1,
        "STAGNANT": 1,
    }
    stored = m1_seeded.stock.by_run(result.run.run_id)
    stockout = next(diff for diff in stored["diffs"] if diff["diff_type"] == "STOCKOUT")
    assert stockout["sku"] == "SKU-B"
    assert stockout["platform_available"] == 0
    assert stockout["erp_available"] == 30
    # 三方快照时间分别保留
    assert stockout["platform_snapshot_at"] != stockout["erp_snapshot_at"]
    replenish = next(
        suggestion
        for suggestion in stored["suggestions"]
        if suggestion["action"] == "REPLENISH"
    )
    assert replenish["quantity"] >= 30


def test_s07_suggestion_accept_via_api(
    m1_seeded: AppContainer, m1_client: TestClient, m1_headers: dict[str, str]
) -> None:
    run_scene(m1_seeded, "S07", day="2026-11-25")
    suggestions = m1_client.get("/api/v1/inventory/suggestions", headers=m1_headers).json()
    assert suggestions["items"]
    suggestion_id = suggestions["items"][0]["suggestion_id"]
    accepted = m1_client.post(
        f"/api/v1/inventory/suggestions/{suggestion_id}/accept",
        json={"note": "已通知采购"},
        headers=m1_headers,
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"


def test_p02_p03_read_endpoints(
    m1_seeded: AppContainer, m1_client: TestClient, m1_headers: dict[str, str]
) -> None:
    run_scene(m1_seeded, "S05", day="2026-11-25")
    run_scene(m1_seeded, "S07", day="2026-11-25")
    tickets = m1_client.get("/api/v1/reviews/tickets", headers=m1_headers).json()
    assert tickets["counts"] == {"OPEN": 1}
    assert tickets["items"][0]["review_id"] == "RV-002"
    summary = m1_client.get("/api/v1/reviews/summary", headers=m1_headers).json()
    assert summary["trend"], "DSR 趋势不能为空"
    inventory = m1_client.get("/api/v1/inventory/reconciliation", headers=m1_headers).json()
    assert inventory["counts"]["STOCKOUT"] == 1
    assert inventory["snapshot_note"].startswith("平台/ERP/WMS")
    empty = m1_client.get("/api/v1/workbench/cards?page=P03", headers=m1_headers).json()
    assert empty["cards"][0]["card_id"] == "card.stock_alert"


def test_release_gate_blocks_without_evidence(
    m1_seeded: AppContainer, m1_client: TestClient, m1_headers: dict[str, str]
) -> None:
    response = m1_client.post("/api/v1/metric-cards/gmv/release", headers=m1_headers)
    assert response.status_code == 403
    body = response.json()
    checks = {item["name"]: item["passed"] for item in body["details"]["release"]["checks"]}
    assert checks["probe"] is False and checks["evidence"] is False
    assert "发布自检未通过" in body["message"]


def test_release_gate_passes_after_daily_run(
    m1_seeded: AppContainer, m1_client: TestClient, m1_headers: dict[str, str]
) -> None:
    run_scene(m1_seeded, "S01", day="2026-11-25")
    response = m1_client.post("/api/v1/metric-cards/gmv/release", headers=m1_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["gate_passed"] is True
    assert len(body["checks"]) == 5
    listed = m1_client.get("/api/v1/metric-cards", headers=m1_headers).json()
    gmv = next(item for item in listed["items"] if item["metric_code"] == "gmv")
    assert gmv["release"]["gate_passed"] is True


def test_subscription_crud(
    m1_client: TestClient, m1_headers: dict[str, str]
) -> None:
    created = m1_client.post(
        "/api/v1/subscriptions",
        json={
            "name": "日报订阅",
            "event": "EVT-01",
            "receiver": "owner",
            "channel": "CONSOLE",
            "window": "昨日",
            "thresholds": {"cvr_min": 0.6},
        },
        headers=m1_headers,
    )
    assert created.status_code == 200, created.text
    subscription_id = created.json()["id"]
    listed = m1_client.get("/api/v1/subscriptions", headers=m1_headers).json()
    assert listed["items"][0]["name"] == "日报订阅"
    duplicated = m1_client.post(
        "/api/v1/subscriptions",
        json={"name": "重复", "event": "EVT-01", "receiver": "owner"},
        headers=m1_headers,
    )
    assert duplicated.status_code == 409
    removed = m1_client.delete(f"/api/v1/subscriptions/{subscription_id}", headers=m1_headers)
    assert removed.status_code == 200
    assert m1_client.get("/api/v1/subscriptions", headers=m1_headers).json()["items"] == []


def test_n8n_command_acl(
    m1_seeded: AppContainer, m1_client: TestClient
) -> None:
    token = (m1_seeded.settings.storage_dir / "worker.token").read_text(encoding="utf-8").strip()
    headers = {"X-Api-Token": token}
    accepted = m1_client.post(
        "/api/v1/n8n/command",
        json={"command": "job.start", "scene": "S05", "day": "2026-11-25", "requested_by": "canvas"},
        headers=headers,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["scene"] == "S05"
    assert accepted.json()["status"] == "SUCCEEDED"
    denied_scene = m1_client.post(
        "/api/v1/n8n/command",
        json={"command": "job.start", "scene": "S02", "day": "2026-11-25"},
        headers=headers,
    )
    assert denied_scene.status_code == 400
    assert denied_scene.json()["code"] == "E006"
    no_token = m1_client.post(
        "/api/v1/n8n/command", json={"command": "job.start", "scene": "S01"}
    )
    assert no_token.status_code == 401


def test_m0_ceiling_blocks_l1_modules(m1_container: AppContainer) -> None:
    from kernel.module_loader import ModuleLoader
    from kernel.registry import ExtensionPointRegistry
    from shared.gate_level import GateLevel

    loader = ModuleLoader(
        [m1_container.settings.modules_dir],
        registry=ExtensionPointRegistry(),
        platform_gate_max=GateLevel.L0_READ_ONLY,
        credential_scopes={"demo:report:read", "pdd:report:read"},
    )
    report = loader.run()
    blocked = {issue.module: issue.message for issue in report.blocked}
    assert "mod_review_patrol" in blocked
    assert "gate_level_max=L1" in blocked["mod_review_patrol"]
    assert "mod_stock_recon" in blocked


def test_subscription_receives_daily_report(
    m1_seeded: AppContainer, m1_client: TestClient, m1_headers: dict[str, str]
) -> None:
    created = m1_client.post(
        "/api/v1/subscriptions",
        json={"name": "值班订阅", "event": "EVT-01", "receiver": "viewer"},
        headers=m1_headers,
    )
    assert created.status_code == 200, created.text
    run_scene(m1_seeded, "S01", day="2026-11-25")
    receivers = {
        item["receiver"]
        for item in m1_seeded.notification_log.recent(20)
        if item["event"] == "EVT-01"
    }
    assert {"owner", "viewer"} <= receivers


def test_modules_endpoint_lists_bundle(
    m1_client: TestClient, m1_headers: dict[str, str]
) -> None:
    payload = m1_client.get("/api/v1/modules", headers=m1_headers).json()
    names = {module["name"] for module in payload["modules"]}
    assert "mod_review_patrol" in names and "mod_stock_recon" in names
    assert payload["bundles"] and payload["bundles"][0]["name"] == "bundle_daily_ops"
    assert payload["bundles"][0]["depends"]


def test_worker_heartbeat_and_registration(
    m1_client: TestClient, m1_headers: dict[str, str]
) -> None:
    assert m1_client.get("/api/v1/workers", headers=m1_headers).json()["items"] == []
    registered = m1_client.post("/api/v1/worker/register-demo", headers=m1_headers)
    assert registered.status_code == 200
    workers = m1_client.get("/api/v1/workers", headers=m1_headers).json()
    assert workers["online"] == 1
    assert workers["items"][0]["capabilities"]


def test_n8n_unknown_command_is_rejected_and_logged(
    m1_seeded: AppContainer, m1_client: TestClient
) -> None:
    token = (m1_seeded.settings.storage_dir / "worker.token").read_text(encoding="utf-8").strip()
    response = m1_client.post(
        "/api/v1/n8n/command",
        json={"command": "write.price", "scene": "S01", "day": "2026-11-25"},
        headers={"X-Api-Token": token},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "E003"
    logs = m1_seeded.n8n_commands.recent(5)
    assert logs[0]["command"] == "write.price"
    assert logs[0]["accepted"] is False
