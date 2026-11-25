"""日报读模型构建（DWS + 口径定义 → 表格视图）。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kernel.contexts.metric_data.domain.metric_definition import format_decimal, to_decimal
from kernel.contexts.metric_data.domain.ports import DwsRepository, MetricRepository
from kernel.contexts.metric_data.domain.report import (
    DailyReportRow,
    DailyReportView,
    ReportCell,
    ReportColumn,
)
from kernel.contexts.orchestration.domain.run import Run
from shared.types.values import Channel


class DailyReportBuilder:
    def __init__(self, metrics: MetricRepository, dws: DwsRepository) -> None:
        self.metrics = metrics
        self.dws = dws

    def build(self, run: Run, channel: Channel) -> DailyReportView:
        definitions = sorted(
            self.metrics.definitions(run.platform), key=lambda d: (d.display_order, d.metric_code)
        )
        columns = [
            ReportColumn(
                key=d.metric_code,
                label=d.display_name,
                unit=d.unit,
                precision=d.precision,
                additivity=d.additivity,
                metric_version=d.version,
                display_order=d.display_order,
                null_policy=d.null_policy,
                source=d.source_mapping,
                drill=f"metric.{d.metric_code}",
            )
            for d in definitions
        ]
        versions = sorted({d.version for d in definitions})
        metric_version = f"v{versions[0]}" if len(versions) == 1 else "mixed"

        rows_raw = self.dws.by_run(run.run_id)
        by_date: dict[str, dict[str, Any]] = {}
        for item in rows_raw:
            key = item["stat_date"]
            key = key.isoformat() if hasattr(key, "isoformat") else str(key)
            by_date.setdefault(key, {})[item["metric_code"]] = item

        rows: list[DailyReportRow] = []
        for stat_date in sorted(by_date):
            cells: dict[str, ReportCell] = {}
            for column in columns:
                raw = by_date[stat_date].get(column.key)
                if raw is None or raw.get("value") is None:
                    reason = (raw or {}).get("null_reason") or column.null_policy.value
                    cells[column.key] = ReportCell(
                        metric_code=column.key,
                        value=reason,
                        raw=None,
                        null_reason=reason,
                    )
                    continue
                value = to_decimal(raw["value"])
                cells[column.key] = ReportCell(
                    metric_code=column.key,
                    value=format_decimal(value, column.precision),
                    raw=str(value),
                    null_reason=None,
                )
            rows.append(
                DailyReportRow(stat_date=datetime.fromisoformat(stat_date).date(), cells=cells)
            )

        return DailyReportView(
            platform=run.platform,
            shop_id=run.shop_id,
            window=run.window,
            metric_version=metric_version,
            run_id=run.run_id.value,
            generated_at=datetime.now(UTC),
            channel=channel,
            columns=columns,
            rows=rows,
            data_state="NORMAL" if rows else "EMPTY",
            meta={
                "app_id": run.app_id,
                "scene": run.scene,
                "gate_level_max": run.gate_level_max.value,
                "config_snapshot_hash": run.config_snapshot.hash,
            },
        )
