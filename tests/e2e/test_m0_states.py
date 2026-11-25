"""M0 功能验收 F-01~F-06：上下文、状态、待办超时、模块摘除、只读与错误态。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from bootstrap.container import AppContainer, run_daily
from kernel.contexts.approval.application.use_cases import ExpireApprovalsUseCase
from kernel.contexts.approval.domain.approval_task import ApprovalStatus, ApprovalTask
from shared.gate_level import GateLevel


def _create_demo_task(container: AppContainer, *, expired: bool) -> ApprovalTask:
    run = run_daily(container, day="2026-11-25").run
    now = datetime.now(UTC)
    task = ApprovalTask.request(
        run_id=run.run_id,
        gate_level=GateLevel.L2_MANUAL_APPROVAL,
        action_code="S02.price_update",
        write_plan={
            "rows": [{"target": "SKU-A", "field": "活动价", "before": "¥89.00", "after": "¥79.00"}],
            "evidence": [{"kind": "metric_card", "ref": "metric.cvr@1.0", "label": "口径卡引用"}],
            "rollback_plan": "改回上一稳定价",
            "created_at": now.isoformat(),
        },
        sla_expires_at=now + timedelta(seconds=-60 if expired else 120),
        idempotency_key=f"f04:{expired}:{now.timestamp()}",
        scene="S02",
        platform="demo",
        shop_id="SHOP-0001",
        impact_scope="金额区间 ¥2,400–3,100 · 跨 2 店铺",
    )
    container.approvals.add(task)
    return task


def test_f01_contexts_nav_and_cards(
    client: TestClient, owner_headers: dict[str, str], daily_run
) -> None:
    contexts = client.get("/api/v1/workbench/contexts", headers=owner_headers).json()
    assert set(contexts) >= {"platforms", "shops", "windows", "metric_versions", "readonly"}
    assert contexts["readonly"] is True
    assert contexts["default"]["platform"] == "demo"

    nav = client.get("/api/v1/workbench/nav", headers=owner_headers).json()
    pages = {page["page_id"]: page for page in nav["pages"]}
    assert set(pages) >= {"P01", "P05", "P06", "P09"}
    assert pages["P01"]["available"] is True
    assert "card.daily_report" in pages["P01"]["card_ids"]
    assert pages["P02"]["available"] is False

    cards = client.get("/api/v1/workbench/cards?page=P01", headers=owner_headers).json()
    assert [card["card_id"] for card in cards["cards"]] == [
        "card.daily_report",
        "card.metric_alert",
    ]
    # 全局上下文变化会带 platform/shop 参数重新查询
    other = client.get(
        "/api/v1/reports/latest", params={"platform": "demo", "shop_id": "SHOP-0001"},
        headers=owner_headers,
    )
    assert other.status_code == 200


def test_f02_zero_denominator_and_non_additive(
    client: TestClient, owner_headers: dict[str, str], daily_run
) -> None:
    report = client.get("/api/v1/reports/latest", headers=owner_headers).json()
    cells = report["rows"][0]["cells"]
    assert cells["inventory_turnover"]["value"] == "—"
    assert cells["inventory_turnover"]["null_reason"] == "—"
    ratios = {column["key"] for column in report["columns"] if column["additivity"] == "RATIO"}
    assert {"aov", "cvr", "roi"} <= ratios
    for key in ratios:
        assert "不可加" in next(c for c in report["columns"] if c["key"] == key)["additivity_label"]
    # 空态 ≠ 取数失败：把适配器替换为「平台确实无数据」（empty_ok）再跑一次
    from kernel.contexts.metric_data.domain.ports import RawPayload
    from shared.types.values import Channel

    container = client.app.state.container
    adapter = container.adapters["demo"]
    original_fetch = adapter.fetch

    def empty_fetch(spec, channel: Channel) -> RawPayload:
        return RawPayload(
            platform=spec.platform,
            shop_id=spec.shop_id,
            dataset=spec.dataset,
            channel=Channel.BACKEND_EXPORT,
            records=[],
            payload_hash="empty",
            meta={"empty_ok": True, "source": "empty-window"},
        )

    adapter.fetch = empty_fetch  # type: ignore[method-assign]
    try:
        empty = run_daily(container, day="2026-01-01")
    finally:
        adapter.fetch = original_fetch  # type: ignore[method-assign]
    assert empty.run.status.value == "SUCCEEDED", empty.run.err_code
    empty_report = client.get("/api/v1/reports/latest", headers=owner_headers).json()
    assert empty_report["data_state"] == "EMPTY"
    assert empty_report["empty_copy"] == "该时间窗暂无数据（非取数失败）"
    assert empty_report["rows"] == []


def test_f04_overdue_l2_is_expired_not_executed(
    client: TestClient, seeded: AppContainer, owner_headers: dict[str, str]
) -> None:
    task = _create_demo_task(seeded, expired=True)
    expired = ExpireApprovalsUseCase(seeded.approvals, clock=seeded.clock)()
    assert task.task_id in expired
    reloaded = seeded.approvals.get(task.task_id)
    assert reloaded is not None and reloaded.status is ApprovalStatus.EXPIRED
    # 不签发 token、不产生执行记录
    assert reloaded.evidence is None
    write = client.post(
        "/api/v1/write",
        json={"task_id": task.task_id, "token": "wt_none", "change_order_no": "CO-NONE"},
        headers=owner_headers,
    )
    assert write.status_code == 403

    todos = client.get("/api/v1/todos", headers=owner_headers).json()
    item = next(item for item in todos["items"] if item["todo_id"] == task.task_id)
    assert item["status"] == "EXPIRED"

    detail = client.get(f"/api/v1/change-orders/{task.task_id}", headers=owner_headers).json()
    assert detail["readonly"] is True
    assert detail["readonly_copy"] == "需审批后执行（当前只读模式）"
    assert len(detail["before_after"]) == 1
    assert detail["header"]["write_plan_hash"]


def test_f05_disable_module_removes_cards_without_residue(
    client: TestClient, owner_headers: dict[str, str], daily_run
) -> None:
    response = client.post("/api/v1/modules/mod_daily_report/disable", headers=owner_headers)
    assert response.status_code == 200
    nav = client.get("/api/v1/workbench/nav", headers=owner_headers).json()
    page = next(page for page in nav["pages"] if page["page_id"] == "P01")
    assert page["available"] is False
    assert page["card_ids"] == []
    cards = client.get("/api/v1/workbench/cards?page=P01", headers=owner_headers).json()
    assert cards["cards"] == []
    modules = client.get("/api/v1/modules", headers=owner_headers).json()
    daily = next(m for m in modules["modules"] if m["name"] == "mod_daily_report")
    assert daily["enabled"] is False


def test_f06_readonly_and_error_states(
    client: TestClient, owner_headers: dict[str, str], viewer_headers: dict[str, str], daily_run
) -> None:
    report = client.get("/api/v1/reports/latest", headers=owner_headers).json()
    assert report["readonly"] is True

    # 未授权字段/未找到运行 → 结构化错误，不静默成功
    missing = client.get("/api/v1/runs/run_0123456789abcdef", headers=owner_headers)
    assert missing.status_code in {404, 422}
    if missing.status_code == 422:
        missing = client.get(
            "/api/v1/runs/run_ffffffffffffffff", headers=owner_headers
        )
    assert missing.status_code == 404
    body = missing.json()
    assert body["code"] in {"E008", "E006"}
    assert body["layer"] in {"SYS", "DATA", "CODE", "UI"}
    assert body["user_message"]

    # VIEWER 不能触发运行、不能看审计、不能禁模块
    start = client.post(
        "/api/v1/job/start",
        json={
            "app_id": "app_demo_daily", "scene": "S01", "platform": "demo",
            "shop_id": "SHOP-0001", "window_start": "2026-11-25",
            "window_end": "2026-11-25", "idempotency_key": "viewer-attempt",
        },
        headers=viewer_headers,
    )
    assert start.status_code == 403
    assert start.json()["code"] == "E003"
    assert client.get("/api/v1/audit", headers=viewer_headers).status_code == 403
    assert (
        client.post("/api/v1/modules/mod_daily_report/disable", headers=viewer_headers).status_code
        == 403
    )


def test_core_module_cannot_be_disabled(
    client: TestClient, owner_headers: dict[str, str]
) -> None:
    response = client.post("/api/v1/modules/mod_core/disable", headers=owner_headers)
    assert response.status_code == 403
    assert response.json()["code"] == "E007"


def test_contexts_are_filtered_by_shop_scope(
    client: TestClient, owner_headers: dict[str, str], viewer_headers: dict[str, str], daily_run
) -> None:
    owner_contexts = client.get("/api/v1/workbench/contexts", headers=owner_headers).json()
    assert set(owner_contexts["platforms"]) == {"demo", "pdd"}
    viewer_contexts = client.get("/api/v1/workbench/contexts", headers=viewer_headers).json()
    assert viewer_contexts["platforms"] == ["demo"]
