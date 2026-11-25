"""口径卡发布门禁：五项自检（分母、映射、枚举/策略、探针、证据包）。

任何一项失败 → 不发布、不覆盖既有版本，返回 409（E007）。
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from kernel.contexts.metric_data.domain.metric_definition import (
    FormulaEvaluator,
    MetricDefinition,
    MetricCalculator,
)
from kernel.contexts.metric_data.domain.release import (
    ProbeRunner,
    ReleaseCheck,
    ReleaseResult,
)
from kernel.contexts.metric_data.domain.report import DailyReportView
from shared.errors.registry import DomainError
from shared.types.values import Additivity, NullReason

FORBIDDEN_SQL = re.compile(r";|\b(insert|update|delete|drop|alter|grant)\b", re.IGNORECASE)
ALLOWED_SOURCES = ("dwd_", "dws_", "计算列", "erp", "wms", "demo", "platform", "adapter")
ALLOWED_NULL_POLICIES = {reason.name for reason in NullReason}


class MetricReleaseService:
    def __init__(self, probes: ProbeRunner) -> None:
        self.probes = probes

    def run(
        self,
        definition: MetricDefinition,
        *,
        card_payload: dict[str, Any] | None,
        view: DailyReportView | None,
        run_id: str | None,
        checked_by: str,
        sample_values: dict[str, Any] | None = None,
    ) -> ReleaseResult:
        checks = [
            self._check_formula(definition, sample_values or {}),
            self._check_mapping(definition, card_payload or {}),
            self._check_policy(definition),
            self._check_probe(definition, run_id),
            self._check_evidence(definition, view, run_id),
        ]
        return ReleaseResult(
            metric_code=definition.metric_code,
            version=definition.version,
            passed=all(check.passed for check in checks),
            checks=checks,
            checked_at=datetime.now(UTC),
            checked_by=checked_by,
        )

    # ------------------------------------------------------------------ 1 formula
    @staticmethod
    def _check_formula(
        definition: MetricDefinition, sample_values: dict[str, Any]
    ) -> ReleaseCheck:
        names = FormulaEvaluator.names(definition.formula)
        if not names:
            return ReleaseCheck("formula", False, "公式为空")
        if definition.formula.count("/") > 0 and not definition.denominator:
            # 允许除法，但分母必须显式声明，避免零分母静默
            return ReleaseCheck("formula", False, "公式含除法但未声明 denominator")
        filled = {name: sample_values.get(name, 1) for name in names}
        try:
            MetricCalculator().compute(
                [definition],
                filled,
                {name: NullReason.NO_DATA for name in names if sample_values.get(name) is None},
            )
        except DomainError as exc:
            return ReleaseCheck("formula", False, exc.message)
        return ReleaseCheck("formula", True, f"变量 {','.join(sorted(names))} 可求值")

    # ------------------------------------------------------------------ 2 mapping
    @staticmethod
    def _check_mapping(definition: MetricDefinition, card: dict[str, Any]) -> ReleaseCheck:
        source = definition.source_mapping.strip()
        if not source:
            return ReleaseCheck("mapping", False, "source_mapping 为空")
        if not source.startswith(ALLOWED_SOURCES):
            return ReleaseCheck("mapping", False, f"source_mapping 无法归到已知分区: {source}")
        if "TODO" in source or "TBD" in source:
            return ReleaseCheck("mapping", False, f"source_mapping 存在占位: {source}")
        if card and card.get("metric_code") not in (None, definition.metric_code):
            return ReleaseCheck("mapping", False, "口径卡 metric_code 与定义不一致")
        return ReleaseCheck("mapping", True, source)

    # ------------------------------------------------------------------ 3 policy
    @staticmethod
    def _check_policy(definition: MetricDefinition) -> ReleaseCheck:
        if definition.null_policy.name not in ALLOWED_NULL_POLICIES:
            return ReleaseCheck("policy", False, f"未知 null_policy: {definition.null_policy}")
        if not definition.unit:
            return ReleaseCheck("policy", False, "unit 为空")
        if definition.precision < 0 or definition.precision > 6:
            return ReleaseCheck("policy", False, f"precision 越界: {definition.precision}")
        if definition.additivity is Additivity.ADDITIVE and definition.formula.count("/") > 0:
            return ReleaseCheck("policy", False, "含除法的指标不应标 ADDITIVE")
        return ReleaseCheck("policy", True, f"{definition.additivity.value}/{definition.null_policy.name}")

    # ------------------------------------------------------------------ 4 probe
    def _check_probe(self, definition: MetricDefinition, run_id: str | None) -> ReleaseCheck:
        sql = definition.probe_sql_template.strip()
        if not sql:
            return ReleaseCheck("probe", False, "缺少探针 SQL")
        if not sql.lower().startswith("select"):
            return ReleaseCheck("probe", False, "探针只允许 SELECT")
        if FORBIDDEN_SQL.search(sql):
            return ReleaseCheck("probe", False, "探针包含多语句或写操作")
        if not run_id:
            return ReleaseCheck("probe", False, "没有可用的 run_id，无法执行探针")
        try:
            value = self.probes.run(sql, {"run_id": run_id})
        except Exception as exc:  # noqa: BLE001 - 探针失败原因要回显给发布人
            return ReleaseCheck("probe", False, f"探针执行失败: {exc}")
        if value is None:
            return ReleaseCheck("probe", False, "探针无返回：该口径当前没有可发布证据")
        return ReleaseCheck("probe", True, f"返回 {value!r}")

    # ------------------------------------------------------------------ 5 evidence
    @staticmethod
    def _check_evidence(
        definition: MetricDefinition, view: DailyReportView | None, run_id: str | None
    ) -> ReleaseCheck:
        if view is None or run_id is None:
            return ReleaseCheck("evidence", False, "缺少 run_id / 报表证据")
        if view.data_state == "EMPTY":
            return ReleaseCheck("evidence", False, "该时间窗无数据，不能作为发布证据")
        cell_present = any(
            definition.metric_code in row.cells for row in view.rows
        )
        if not cell_present:
            return ReleaseCheck("evidence", False, "报表明细未包含该指标")
        return ReleaseCheck("evidence", True, f"run_id={run_id} 报表明细含 {definition.metric_code}")
