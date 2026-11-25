"""Run 聚合与配置快照单测。"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from kernel.contexts.orchestration.domain.config_snapshot import ConfigSnapshot
from kernel.contexts.orchestration.domain.run import (
    NodeExecution,
    NodeStatus,
    Run,
    RunStatus,
)
from shared.errors.registry import DomainError
from shared.gate_level import GateLevel
from shared.run_id import RunId
from shared.types.values import StatWindow


def _run() -> Run:
    return Run(
        run_id=RunId.new(),
        app_id="app_demo_daily",
        scene="S01",
        platform="demo",
        shop_id="SHOP-0001",
        window=StatWindow(date(2026, 11, 25), date(2026, 11, 25)),
        trigger_type="MANUAL",
        config_snapshot=ConfigSnapshot.build({"metric_versions": [{"code": "gmv", "version": "1.0"}]}),
        gate_level_max=GateLevel.L0_READ_ONLY,
    )


def test_happy_path_state_machine() -> None:
    run = _run()
    now = datetime.now(UTC)
    run.start(now)
    assert run.status is RunStatus.RUNNING
    run.record_node(NodeExecution("T0", NodeStatus.SUCCEEDED, cost_ms=1))
    run.succeed(now)
    assert run.status is RunStatus.SUCCEEDED
    assert run.ended_at is not None
    with pytest.raises(DomainError):
        run.start(now)


def test_fail_requires_registered_code_and_layer() -> None:
    run = _run()
    now = datetime.now(UTC)
    run.start(now)
    with pytest.raises(DomainError):
        run.fail("E999", "DATA", now)
    run.fail("E004", None, now)
    assert run.err_code == "E004"
    assert run.err_layer == "DATA"
    with pytest.raises(DomainError):
        run.succeed(now)


def test_failed_node_must_carry_error_code() -> None:
    run = _run()
    run.start(datetime.now(UTC))
    with pytest.raises(DomainError):
        run.record_node(NodeExecution("T1", NodeStatus.FAILED))
    run.record_node(NodeExecution("T1", NodeStatus.FAILED, err_code="E005", err_layer="SYS"))


def test_config_snapshot_is_immutable_and_hashed() -> None:
    snapshot = ConfigSnapshot.build({"b": 2, "a": 1})
    assert snapshot.hash == ConfigSnapshot.build({"a": 1, "b": 2}).hash
    with pytest.raises(TypeError):
        snapshot.payload["a"] = 3  # type: ignore[index]
    assert snapshot.get("missing", "fallback") == "fallback"


def test_events_are_pulled_once() -> None:
    run = _run()
    run.start(datetime.now(UTC))
    run.succeed(datetime.now(UTC))
    events = run.pull_events()
    assert [e.event_type for e in events] == ["RunStarted", "RunSucceeded"]
    assert run.pull_events() == []
