"""S01 端到端：触发 → 取数 → 标准化 → 计算 → 出报 → 推送 → 归档 → 下钻。"""
from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from bootstrap.container import AppContainer


def test_s01_full_chain_and_three_step_drilldown(
    seeded: AppContainer, client: TestClient, owner_headers: dict[str, str], daily_run
) -> None:
    run = daily_run.run
    assert run.status.value == "SUCCEEDED"

    report = client.get("/api/v1/reports/latest", headers=owner_headers).json()
    assert report["data_state"] == "NORMAL"
    assert report["metric_version"] == "v1.0"
    assert len(report["columns"]) == 12
    assert len(report["rows"]) == 1
    cells = report["rows"][0]["cells"]
    assert cells["gmv"]["value"] == "2,460.00"
    assert cells["gmv"]["null_reason"] is None
    assert cells["inventory_turnover"]["value"] == "—"
    assert cells["cvr"]["value"] == "0.50"

    ratio_columns = [c for c in report["columns"] if c["additivity"] == "RATIO"]
    assert ratio_columns and all(c["additivity_label"] == "不可加（比率类）" for c in ratio_columns)
    assert report["channel_label"] == "后台导出"
    assert run.run_id.value in report["watermark"]
    assert "已脱敏" in report["watermark"]
    assert report["alerts"], "cvr 0.50 < 0.6 应触发告警"

    # 第一步：指标 → 口径卡
    card = client.get("/api/v1/metric-cards/gmv", headers=owner_headers)
    assert card.status_code == 200
    card_body = card.json()
    assert card_body["compute"]["formula"] == "gmv"
    assert card_body["compute"]["additivity"] == "ADDITIVE"
    assert card_body["evidence"]["probe_sql_template"]
    assert card_body["evidence"]["last_inspected_value"]["stat_date"] == "2026-11-25"

    # 第二步：run_id
    run_detail = client.get(f"/api/v1/runs/{report['run_id']}", headers=owner_headers)
    assert run_detail.status_code == 200
    run_body = run_detail.json()
    assert [node["node_id"] for node in run_body["nodes"]] == [
        "T0", "T1", "T2", "T3", "T4", "T5", "T6",
    ]
    assert run_body["ods"], "ODS 证据列表不能为空"

    # 第三步：ODS 原始证据（默认脱敏）
    payload_id = run_body["ods"][0]["id"]
    evidence = client.get(
        f"/api/v1/runs/{report['run_id']}/evidence/{payload_id}", headers=owner_headers
    )
    assert evidence.status_code == 200
    body = evidence.json()
    assert body["masked"] is True
    assert body["masked_copy"] == "买家信息已脱敏，原文证据仅审计角色可见"
    assert "13812345678" not in str(body["payload"])


def test_export_contains_watermark_and_13_columns(
    client: TestClient, owner_headers: dict[str, str], daily_run
) -> None:
    report = client.get("/api/v1/reports/latest", headers=owner_headers).json()
    response = client.get(f"/api/v1/reports/{report['report_id']}/export", headers=owner_headers)
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook.active
    assert "run_id" in str(sheet["A1"].value)
    assert "已脱敏" in str(sheet["A1"].value)
    header = [sheet.cell(row=4, column=column).value for column in range(1, 16)]
    assert header[0] == "平台 / 店铺"
    assert header[1] == "统计日期"
    assert any("GMV" in str(item) for item in header)
    assert any("不可加" in str(item) for item in header)


def test_worker_api_write_is_disabled_and_query_works(
    client: TestClient, owner_headers: dict[str, str], daily_run
) -> None:
    run_id = daily_run.run.run_id.value
    query = client.get(f"/api/v1/job/query?run_id={run_id}", headers=owner_headers)
    assert query.status_code == 200
    assert query.json()["status"] == "SUCCEEDED"
    assert query.json()["gate_level_max"] == "L0"

    write = client.post(
        "/api/v1/write",
        json={"task_id": "task_x", "token": "wt_x", "change_order_no": "CO-1"},
        headers=owner_headers,
    )
    assert write.status_code == 403
    assert write.json()["code"] == "E007"
    assert "写入必须经闸门" in write.json()["message"]


def test_job_start_is_idempotent_over_http(
    seeded: AppContainer, client: TestClient, owner_headers: dict[str, str]
) -> None:
    payload = {
        "app_id": "app_demo_daily",
        "scene": "S01",
        "platform": "demo",
        "shop_id": "SHOP-0001",
        "window_start": "2026-11-25",
        "window_end": "2026-11-25",
        "trigger_type": "MANUAL",
        "idempotency_key": "http-idem-2026-11-25",
    }
    first = client.post("/api/v1/job/start", json=payload, headers=owner_headers)
    second = client.post("/api/v1/job/start", json=payload, headers=owner_headers)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["run_id"] == second.json()["run_id"]
    assert second.json()["deduplicated"] is True
    assert len(seeded.runs.recent(10)) == 1


def test_machine_token_can_start_job_but_cannot_write(
    seeded, client: TestClient
) -> None:
    token_file = seeded.settings.storage_dir / "worker.token"
    assert token_file.is_file()
    headers = {"X-Api-Token": token_file.read_text(encoding="utf-8").strip()}
    response = client.post(
        "/api/v1/job/start",
        json={
            "app_id": "app_demo_daily",
            "scene": "S01",
            "platform": "demo",
            "shop_id": "SHOP-0001",
            "window_start": "2026-11-25",
            "window_end": "2026-11-25",
            "trigger_type": "SCHEDULE",
            "idempotency_key": "machine-token-run",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCEEDED"
    assert response.json()["deduplicated"] is False
    write = client.post(
        "/api/v1/write",
        json={"task_id": "t", "token": "w", "change_order_no": "c"},
        headers=headers,
    )
    assert write.status_code == 403
