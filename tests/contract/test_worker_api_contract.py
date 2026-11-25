"""Worker API 契约测试：schema 快照、请求校验、错误信封、/write 拒绝。"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from kernel.contracts.worker_api import (
    JobStartRequest,
    JobStartResponse,
    NodeStatus,
    TriggerType,
    CallbackRequest,
)
from scripts.gen_schemas import CONTRACTS, main as generate_schemas

ROOT = Path(__file__).resolve().parents[2]


def test_schema_snapshot_is_up_to_date(tmp_path: Path) -> None:
    before = {path.name: path.read_text(encoding="utf-8") for path in CONTRACTS.glob("*.json")}
    assert before, "docs/contracts 下没有 schema，先运行 scripts/gen_schemas.py"
    assert generate_schemas() == 0
    after = {path.name: path.read_text(encoding="utf-8") for path in CONTRACTS.glob("*.json")}
    assert before == after, "契约 schema 已变更：请显式更新 docs/contracts 并评估 api_compat"


def test_worker_api_schema_shape() -> None:
    schema = json.loads((CONTRACTS / "worker_api.schema.json").read_text(encoding="utf-8"))
    assert schema["kernel_api"] == "1.0"
    for required in ["JobStartRequest", "JobQueryResponse", "SuggestRequest", "WriteRequest",
                     "CallbackRequest", "ErrorEnvelope"]:
        assert required in schema["types"]
    properties = schema["types"]["ErrorEnvelope"]["properties"]
    assert set(properties) >= {
        "code", "layer", "message", "user_message", "retryable", "details"
    }


def test_job_start_request_rejects_extra_fields_and_inverted_window() -> None:
    with pytest.raises(ValidationError):
        JobStartRequest(
            app_id="app", scene="S01", platform="demo", shop_id="S1",
            window_start=date(2026, 11, 25), window_end=date(2026, 11, 25),
            idempotency_key="k", unknown_field=1,
        )
    with pytest.raises(ValidationError):
        JobStartRequest(
            app_id="app", scene="S01", platform="demo", shop_id="S1",
            window_start=date(2026, 11, 26), window_end=date(2026, 11, 25),
            idempotency_key="k",
        )


def test_job_start_defaults_and_enum_parsing() -> None:
    request = JobStartRequest(
        app_id="app", scene="S01", platform="demo", shop_id="S1",
        window_start=date(2026, 11, 25), window_end=date(2026, 11, 25),
        idempotency_key="daily:demo:S1:2026-11-25", trigger_type="SCHEDULE",
    )
    assert request.trigger_type is TriggerType.SCHEDULE
    assert request.requested_by == "system"


def test_callback_requires_node_status_enum() -> None:
    callback = CallbackRequest(
        run_id="run_0123456789abcdef", node_id="T1", status="SUCCEEDED", cost_ms=10
    )
    assert callback.status is NodeStatus.SUCCEEDED
    with pytest.raises(ValidationError):
        CallbackRequest(run_id="run_0123456789abcdef", node_id="T1", status="WHATEVER")


def test_response_models_are_serializable() -> None:
    response = JobStartResponse(
        run_id="run_0123456789abcdef", status="CREATED", accepted_at="2026-11-25T00:00:00Z"
    )
    assert response.model_dump()["deduplicated"] is False


def test_metric_card_schema_has_required_contract_fields() -> None:
    schema = json.loads((CONTRACTS / "metric_card.schema.json").read_text(encoding="utf-8"))
    required = set(schema["types"]["MetricCardFileSpec"]["required"])
    assert {
        "metric_code", "display_name", "version", "unit", "precision",
        "additivity", "formula",
    } <= required
