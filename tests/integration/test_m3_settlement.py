"""M3 对账切片：S09 结算/毛利对账 + P08 读模型。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from bootstrap.container import AppContainer, run_scene


def test_s09_reconciles_settlement_with_evidence_trace(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    result = run_scene(m2_seeded, "S09", day="2026-11-25")
    assert result.run.status.value == "SUCCEEDED", result.run.err_code
    assert result.scene_result is not None
    assert result.scene_result.details["counts"] == {
        "MATCH": 1,
        "AMOUNT_DIFF": 1,
        "MISSING_SETTLEMENT": 1,
        "MISSING_ORDER": 1,
    }
    stored = m2_seeded.settlements.by_run(result.run.run_id)
    by_order = {item["order_id"]: item for item in stored}
    assert by_order["D0-1001"]["diff_type"] == "MATCH"
    assert by_order["D0-1001"]["delta"] == 0.0
    assert by_order["D0-1002"]["expected_net"] == 717.0
    assert by_order["D0-1002"]["settled_amount"] == 700.0
    assert by_order["D0-1002"]["delta"] == -17.0
    assert by_order["D0-1002"]["order_ref"] == "orders.csv"
    assert by_order["D0-1002"]["settlement_ref"] == "settlement.csv"
    assert by_order["D0-1003"]["diff_type"] == "MISSING_SETTLEMENT"
    assert by_order["D0-1003"]["settled_amount"] is None
    assert by_order["D9-9999"]["diff_type"] == "MISSING_ORDER"
    assert by_order["D9-9999"]["expected_net"] == 0.0

    summary = m2_client.get("/api/v1/settlement/reconciliation", headers=m2_headers).json()
    assert summary["run_id"] == result.run.run_id.value
    assert summary["counts"]["AMOUNT_DIFF"] == 1
    assert summary["totals"]["expected"] == 2257.0
    assert summary["totals"]["settled"] == 2090.0
    assert summary["totals"]["delta"] == -167.0
    assert "财务写入禁止" in summary["note"]
    assert summary["readonly"] is True

    filtered = m2_client.get(
        "/api/v1/settlement/reconciliation", params={"diff_type": "AMOUNT_DIFF"},
        headers=m2_headers,
    ).json()
    assert len(filtered["diffs"]) == 1
    assert filtered["diffs"][0]["order_id"] == "D0-1002"


def test_s09_empty_state_before_any_run(
    m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    payload = m2_client.get("/api/v1/settlement/reconciliation", headers=m2_headers).json()
    assert payload["run_id"] is None
    assert payload["diffs"] == []
    assert payload["empty_copy"] == "无差异"
    assert payload["totals"] == {"expected": 0, "settled": 0, "delta": 0}
