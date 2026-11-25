"""安全验收：PII 不进日志/报表/通知/审计；原文证据仅审计角色且留痕。"""
from __future__ import annotations

import json
from io import BytesIO

from fastapi.testclient import TestClient

from bootstrap.container import AppContainer

PHONES = [
    "13812345678",
    "13987654321",
    "13700001111",
    "13612340000",
    "13512341234",
]
ADDRESS = "上海市浦东新区张江路100号"


def _report_text(container: AppContainer, run_id) -> str:
    report = next(r for r in container.reports.recent(10) if r.run_id == run_id)
    from openpyxl import load_workbook

    data = container.storage.get_bytes(report.artifact_ref)
    workbook = load_workbook(BytesIO(data))
    values = [
        str(cell.value)
        for sheet in workbook.worksheets
        for row in sheet.iter_rows()
        for cell in row
        if cell.value is not None
    ]
    return "\n".join(values) + report.watermark


def test_pii_never_reaches_report_logs_or_notifications(
    seeded: AppContainer, daily_run
) -> None:
    run = daily_run.run
    haystacks = {
        "report": _report_text(seeded, run.run_id),
        "notification": json.dumps(
            [item["payload"] for item in seeded.notification_log.recent(20)], ensure_ascii=False
        ),
        "audit": json.dumps(seeded.audit.recent(50), ensure_ascii=False),
        "exceptions": json.dumps(seeded.exceptions.recent(50), ensure_ascii=False),
    }
    for label, text in haystacks.items():
        for phone in PHONES:
            assert phone not in text, f"{label} 泄露手机号 {phone}"
        assert ADDRESS not in text, f"{label} 泄露收货地址"

    # DWD 只保留脱敏后的昵称
    with seeded.database.session() as session:
        from sqlalchemy import select

        from kernel.persistence.tables import DwdOrder

        nicknames = [
            row.buyer_nickname for row in session.execute(select(DwdOrder)).scalars().all()
        ]
    assert nicknames, "DWD 应有订单"
    assert all(nickname.endswith("***") for nickname in nicknames), nicknames


def test_evidence_default_masked_and_raw_requires_audit_role(
    seeded: AppContainer, client: TestClient, owner_headers, viewer_headers, daily_run
) -> None:
    run_id = daily_run.run.run_id.value
    run = client.get(f"/api/v1/runs/{run_id}", headers=owner_headers).json()
    payload_id = run["ods"][0]["id"]

    masked = client.get(
        f"/api/v1/runs/{run_id}/evidence/{payload_id}", headers=owner_headers
    ).json()
    assert masked["masked"] is True
    assert not any(phone in json.dumps(masked["payload"], ensure_ascii=False) for phone in PHONES)

    # VIEWER 不允许看原文
    denied = client.get(
        f"/api/v1/runs/{run_id}/evidence/{payload_id}?raw=true", headers=viewer_headers
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "E003"

    # OWNER 可看原文，但必须留访问审计
    raw = client.get(
        f"/api/v1/runs/{run_id}/evidence/{payload_id}?raw=true", headers=owner_headers
    )
    assert raw.status_code == 200
    assert raw.json()["masked"] is False
    assert any(
        item["action"] == "evidence.raw_access" for item in seeded.audit.recent(20)
    )


def test_audit_repository_is_append_only_by_design(seeded: AppContainer) -> None:
    from kernel.contexts.observability.infrastructure.repositories import SqlAuditRepository

    public_methods = {
        name for name in dir(SqlAuditRepository) if not name.startswith("_")
    }
    assert "record" in public_methods and "recent" in public_methods
    assert not ({"update", "delete", "remove"} & public_methods)


def test_no_ai_auto_execution_entrypoints_in_routes() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    forbidden = ["auto_execute", "ai_auto", "一键优化", "AI 自动执行"]
    offenders: list[str] = []
    for path in list((root / "src" / "bootstrap").rglob("*.py")) + list(
        (root / "src" / "kernel").rglob("*.py")
    ):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append(f"{path}: {token}")
    assert not offenders, offenders
