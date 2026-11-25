"""仓储与 Outbox 集成测试（SQLite，生产切 PostgreSQL 不改仓储接口）。"""
from __future__ import annotations

from datetime import UTC, datetime

from bootstrap.container import AppContainer, run_daily
from kernel.contexts.approval.domain.approval_task import ApprovalTask
from kernel.contexts.observability.domain.models import AuditEntry
from shared.evidence import EvidenceSet
from shared.gate_level import GateLevel


def test_daily_run_persists_ods_dwd_dws_report(seeded: AppContainer) -> None:
    result = run_daily(seeded, day="2026-11-25")
    run = result.run
    assert run.status.value == "SUCCEEDED"
    assert [node.node_id for node in run.nodes] == ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]

    ods = seeded.ods.by_run(run.run_id)
    assert {item["dataset"] for item in ods} == {"order", "traffic", "ad", "review", "inventory"}

    facts = seeded.dwd.facts("demo", "SHOP-0001", run.window)
    assert len(facts) == 1
    assert facts[0].facts["gmv"] == 2460
    assert facts[0].facts["paid_orders"] == 3

    dws = {row["metric_code"]: row for row in seeded.dws.by_run(run.run_id)}
    assert str(dws["gmv"]["value"]) == "2460.000000"
    assert dws["inventory_turnover"]["null_reason"] == "—"
    assert dws["cvr"]["additivity"] == "RATIO"

    reports = [report for report in seeded.reports.recent(5) if report.run_id == run.run_id]
    assert len(reports) == 1
    assert seeded.storage.exists(reports[0].artifact_ref)
    assert run.run_id.value in reports[0].watermark
    assert "已脱敏" in reports[0].watermark


def test_run_is_idempotent_by_business_key(seeded: AppContainer) -> None:
    first = run_daily(seeded, day="2026-11-25")
    second = run_daily(seeded, day="2026-11-25")
    assert second.deduplicated is True
    assert first.run.run_id == second.run.run_id
    assert len(seeded.runs.recent(10)) == 1


def test_outbox_records_domain_events(seeded: AppContainer) -> None:
    run_daily(seeded, day="2026-11-25")
    pending = seeded.outbox.pending()
    event_types = {item["event_type"] for item in pending}
    assert {"RunStarted", "RunSucceeded"} <= event_types


def test_approval_repository_roundtrip_and_overdue(seeded: AppContainer) -> None:
    run = run_daily(seeded, day="2026-11-25").run
    past = datetime.now(UTC).replace(microsecond=0)
    task = ApprovalTask.request(
        run_id=run.run_id,
        gate_level=GateLevel.L2_MANUAL_APPROVAL,
        action_code="S02.price_update",
        write_plan={"rows": []},
        sla_expires_at=past,
        idempotency_key=f"roundtrip:{past.timestamp()}",
        scene="S02",
        platform="demo",
        shop_id="SHOP-0001",
    )
    seeded.approvals.add(task)
    loaded = seeded.approvals.get(task.task_id)
    assert loaded is not None and loaded.status is task.status
    assert task.task_id in {item.task_id for item in seeded.approvals.overdue(past)}

    evidence = EvidenceSet("owner", past, "CO-1", "before", "after")
    fresh = ApprovalTask.request(
        run_id=run.run_id,
        gate_level=GateLevel.L2_MANUAL_APPROVAL,
        action_code="S02.price_update",
        write_plan={"rows": []},
        sla_expires_at=datetime.now(UTC) + __import__('datetime').timedelta(hours=1),
        idempotency_key=f"roundtrip-2:{past.timestamp()}",
    )
    seeded.approvals.add(fresh)
    fresh.grant(evidence, datetime.now(UTC))
    seeded.approvals.save(fresh)
    reloaded = seeded.approvals.get(fresh.task_id)
    assert reloaded is not None
    assert reloaded.evidence is not None
    assert reloaded.evidence.change_order_no == "CO-1"
    assert reloaded.status.value == "APPROVED"


def test_audit_and_exception_are_queryable(seeded: AppContainer) -> None:
    seeded.audit.record(
        AuditEntry(actor="owner", action="test.action", object_type="test", object_id="1")
    )
    assert any(item["action"] == "test.action" for item in seeded.audit.recent(10))
    from shared.errors.registry import DomainError

    record_id = seeded.exceptions.record(DomainError("E004", "字段漂移"), run_id="run_0123456789abcdef")
    assert record_id >= 1
    assert any(item["err_code"] == "E004" for item in seeded.exceptions.recent(10))


def test_dws_is_same_source_for_report_and_dashboard(seeded: AppContainer) -> None:
    result = run_daily(seeded, day="2026-11-25")
    report = next(r for r in seeded.reports.recent(5) if r.run_id == result.run.run_id)
    view = seeded.report_builder.build(result.run, report.channel)
    assert view.rows and view.rows[0].cells["gmv"].value == "2,460.00"
    assert view.watermark in {"", report.watermark}  # view 的水印由调用方注入
    assert any(column.key == "cvr" for column in view.columns)


def test_failure_goes_to_dead_letter_and_alerts(seeded: AppContainer) -> None:
    from kernel.contexts.integration.domain.models import FetchChannelUnavailable

    adapter = seeded.adapters["demo"]

    def boom(spec, channel):  # type: ignore[no-untyped-def]
        raise FetchChannelUnavailable("模拟：导出文件缺失")

    adapter.fetch = boom  # type: ignore[method-assign]
    result = run_daily(seeded, day="2026-11-25")
    assert result.run.status.value == "FAILED"
    assert result.run.err_code == "E004"
    dead = seeded.dead_letters.recent(5)
    assert any(item["run_id"] == result.run.run_id.value for item in dead)
    notifications = seeded.notification_log.recent(10)
    assert any(
        item["event"] == "EVT-07" and item["payload"].get("err_code") == "E004"
        for item in notifications
    )
