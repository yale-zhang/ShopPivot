"""报表聚合与工作台读模型（主文档表 3-20 / 表 3-25 / 表 3-26）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from kernel.contexts.metric_data.domain.metric_definition import MetricValue
from shared.run_id import RunId
from shared.types.values import Additivity, Channel, NullReason, StatWindow


def new_report_id() -> str:
    return f"rpt_{uuid4().hex[:16]}"


@dataclass(frozen=True, slots=True)
class ReportColumn:
    key: str
    label: str
    unit: str
    precision: int
    additivity: Additivity
    metric_version: str
    display_order: int = 100
    null_policy: NullReason = NullReason.NOT_APPLICABLE
    source: str = ""
    drill: str = ""

    @property
    def additivity_label(self) -> str:
        return self.additivity.label


@dataclass(frozen=True, slots=True)
class ReportCell:
    metric_code: str
    value: str
    raw: str | None
    null_reason: str | None


@dataclass(frozen=True, slots=True)
class DailyReportRow:
    stat_date: date
    cells: dict[str, ReportCell]


@dataclass
class DailyReportView:
    platform: str
    shop_id: str
    window: StatWindow
    metric_version: str
    run_id: str
    generated_at: datetime
    channel: Channel
    columns: list[ReportColumn] = field(default_factory=list)
    rows: list[DailyReportRow] = field(default_factory=list)
    data_state: str = "NORMAL"
    empty_copy: str = "该时间窗暂无数据（非取数失败）"
    watermark: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Report:
    report_id: str
    run_id: RunId
    platform: str
    shop_id: str
    window: StatWindow
    metric_version: str
    artifact_ref: str = ""
    watermark: str = ""
    status: str = "GENERATED"
    channel: Channel = Channel.BACKEND_EXPORT
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    cells: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        run_id: RunId,
        platform: str,
        shop_id: str,
        window: StatWindow,
        metric_version: str,
        channel: Channel,
    ) -> "Report":
        report_id = new_report_id()
        stamp = datetime.now(UTC)
        watermark = (
            f"口径版本 {metric_version} · 生成时间 {stamp.astimezone().strftime('%Y-%m-%d %H:%M')}"
            f" · run_id {run_id.value} · 已脱敏"
        )
        return cls(
            report_id=report_id,
            run_id=run_id,
            platform=platform,
            shop_id=shop_id,
            window=window,
            metric_version=metric_version,
            watermark=watermark,
            channel=channel,
            generated_at=stamp,
        )

    def to_values(self, values: list[MetricValue]) -> None:
        self.cells = [
            {
                "metric_code": v.metric_code,
                "value": v.value,
                "display": v.display,
                "unit": v.unit,
                "precision": v.precision,
                "additivity": v.additivity.value,
                "null_reason": v.null_reason.value if v.null_reason else None,
                "metric_version": v.metric_version,
            }
            for v in values
        ]
