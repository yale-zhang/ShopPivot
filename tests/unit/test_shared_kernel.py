"""共享内核单测：闸门级别 / run_id / 幂等键 / 四要素 / 脱敏 / 配置快照 / 错误码。"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from shared.errors.registry import ERROR_SPECS, DomainError
from shared.evidence import EvidenceSet
from shared.gate_level import GateLevel
from shared.idempotency import IdempotencyKey
from shared.run_id import RunId
from shared.security.masking import (
    NON_EXPORTABLE_FIELDS,
    mask_mapping,
    mask_phone,
    mask_text,
    redact_for_log,
)
from shared.types.values import Additivity, NullReason


def test_gate_level_order_and_parse() -> None:
    assert GateLevel.parse("l2") is GateLevel.L2_MANUAL_APPROVAL
    assert GateLevel.L0_READ_ONLY.at_most(GateLevel.L2_MANUAL_APPROVAL)
    assert not GateLevel.L2_MANUAL_APPROVAL.at_most(GateLevel.L0_READ_ONLY)
    assert GateLevel.L2_MANUAL_APPROVAL.requires_human
    with pytest.raises(ValueError):
        GateLevel.parse("L9")


def test_run_id_format() -> None:
    run_id = RunId.new()
    assert run_id.value.startswith("run_") and len(run_id.value) == 20
    assert RunId.parse(run_id.value) == run_id
    with pytest.raises(ValueError):
        RunId.parse("R-20261124-0801")


def test_idempotency_key_composition() -> None:
    assert IdempotencyKey.sku_daily("SKU-A", "2026-11-25").as_key == "sku_daily:SKU-A@2026-11-25"
    with pytest.raises(ValueError):
        IdempotencyKey("BadScope", "x")


def test_evidence_requires_four_elements() -> None:
    complete = EvidenceSet(
        operator="owner",
        decided_at=datetime.now(UTC),
        change_order_no="CO-1",
        before_shot="shot://before",
        after_shot="shot://after",
    )
    assert complete.complete()
    partial = EvidenceSet("owner", datetime.now(UTC), "", "a", "b")
    assert partial.missing_fields() == ["change_order_no"]


def test_masking_rules() -> None:
    assert mask_phone("13812345678") == "138****5678"
    assert mask_phone("123") == "***"
    assert "13812345678" not in mask_text("联系 13812345678 处理")
    masked = mask_mapping({"buyer_phone": "13812345678", "buyer_nickname": "小明"})
    assert masked["buyer_phone"] == "138****5678"
    assert masked["buyer_nickname"].startswith("小")
    assert "buyer_nickname" in NON_EXPORTABLE_FIELDS
    redacted = redact_for_log({"note": "电话 13987654321", "nested": [{"receiver_phone": "13800000000"}]})
    assert "13987654321" not in str(redacted)
    assert "13800000000" not in str(redacted)


def test_null_reason_and_additivity_labels() -> None:
    assert NullReason.NOT_APPLICABLE.value == "不适用"
    assert NullReason.NOT_SUPPORTED.value == "—"
    assert Additivity.RATIO.label == "不可加（比率类）"


def test_all_error_codes_have_specs_and_layers() -> None:
    assert set(ERROR_SPECS) == {f"E00{i}" for i in range(1, 9)}
    for spec in ERROR_SPECS.values():
        assert spec.default_layer in {"UI", "SYS", "DATA", "CODE"}
        assert spec.http_status >= 400


def test_domain_error_uses_registry_layer() -> None:
    error = DomainError("E004", "字段漂移")
    assert error.layer == "DATA"
    assert error.retryable is False
    payload = error.to_payload()
    assert payload["code"] == "E004" and payload["layer"] == "DATA"
    with pytest.raises(ValueError):
        DomainError("E999", "未登记")
