"""数据口径上下文端口。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol, Sequence

from kernel.contexts.metric_data.domain.canonical_record import CanonicalRecord
from kernel.contexts.metric_data.domain.metric_definition import MetricDefinition
from kernel.contexts.metric_data.domain.report import DailyReportView, Report
from shared.run_id import RunId
from shared.types.values import Channel, NullReason, StatWindow


@dataclass
class RawPayload:
    platform: str
    shop_id: str
    dataset: str
    channel: Channel
    records: list[dict[str, Any]] = field(default_factory=list)
    payload_hash: str = ""
    storage_ref: str = ""
    fetched_at: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class DailyFacts:
    stat_date: date
    facts: dict[str, Any] = field(default_factory=dict)
    missing_reasons: dict[str, NullReason] = field(default_factory=dict)


@dataclass
class DwdWriteResult:
    saved: int = 0
    skipped: int = 0
    datasets: dict[str, int] = field(default_factory=dict)


class MetricRepository(Protocol):
    def definitions(self, platform: str) -> list[MetricDefinition]: ...

    def definition(self, metric_code: str, version: str | None = None) -> MetricDefinition | None: ...

    def upsert_definition(self, definition: MetricDefinition, card_payload: dict[str, Any]) -> None: ...

    def cards(self) -> list[dict[str, Any]]: ...


class OdsRepository(Protocol):
    def save(self, run_id: RunId, raw: RawPayload) -> str: ...

    def by_run(self, run_id: RunId) -> list[dict[str, Any]]: ...

    def get(self, payload_id: int) -> dict[str, Any] | None: ...


class DwdRepository(Protocol):
    def save_records(
        self, run_id: RunId, records: Sequence[CanonicalRecord]
    ) -> DwdWriteResult: ...

    def facts(
        self, platform: str, shop_id: str, window: StatWindow
    ) -> list[DailyFacts]: ...

    def review_trend(
        self, platform: str, shop_id: str, limit: int = 14
    ) -> list[dict[str, Any]]: ...


class DwsRepository(Protocol):
    def save(
        self,
        run_id: RunId,
        platform: str,
        shop_id: str,
        stat_date: date,
        values: Sequence[Any],
        channel: Channel,
    ) -> int: ...

    def by_run(self, run_id: RunId) -> list[dict[str, Any]]: ...


class ReviewTicketRepository(Protocol):
    def exists(self, platform: str, review_id: str) -> bool: ...

    def add(self, ticket: Any) -> None: ...

    def save(self, ticket: Any) -> None: ...

    def get(self, ticket_id: str) -> Any | None: ...

    def list(
        self, *, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]: ...


class StockRepository(Protocol):
    def save(
        self,
        run_id: RunId,
        platform: str,
        shop_id: str,
        diffs: Sequence[Any],
        suggestions: Sequence[Any],
    ) -> tuple[int, int]: ...

    def by_run(self, run_id: RunId) -> dict[str, Any]: ...

    def suggestions(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]: ...

    def resolve_suggestion(self, suggestion_id: str, status: str) -> bool: ...


class SourcingRepository(Protocol):
    def save(self, run_id: RunId, keyword: str, candidates: Sequence[Any]) -> int: ...

    def by_run(self, run_id: RunId) -> list[dict[str, Any]]: ...

    def latest_for_offer(self, offer_id: str) -> dict[str, Any] | None: ...


class PurchaseRepository(Protocol):
    def add(self, order: Any) -> None: ...

    def save(self, order: Any) -> None: ...

    def get(self, plan_id: str) -> Any | None: ...

    def recent(self, limit: int = 50) -> list[Any]: ...


class SettlementRepository(Protocol):
    def save(
        self, run_id: RunId, platform: str, shop_id: str, diffs: Sequence[Any]
    ) -> int: ...

    def by_run(self, run_id: RunId) -> list[dict[str, Any]]: ...


class AdCampaignRepository(Protocol):
    def save(self, run_id: RunId, platform: str, shop_id: str, stat_date: Any, rows: Sequence[Any]) -> int: ...

    def by_run(self, run_id: RunId) -> list[dict[str, Any]]: ...


class MetricReleaseRepository(Protocol):
    def add(self, result: Any) -> None: ...

    def latest(self, metric_code: str, version: str | None = None) -> dict[str, Any] | None: ...


class ReportRepository(Protocol):
    def add(self, report: Report) -> None: ...

    def get(self, report_id: str) -> Report | None: ...

    def recent(self, limit: int = 20) -> list[Report]: ...


class ReportStorage(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str = "") -> str: ...

    def get_bytes(self, ref: str) -> bytes: ...

    def exists(self, ref: str) -> bool: ...


class ReportBuilder(Protocol):
    def build(self, run_id: RunId, **kwargs: Any) -> DailyReportView: ...


__all__ = [
    "RawPayload",
    "DailyFacts",
    "DwdWriteResult",
    "MetricRepository",
    "OdsRepository",
    "DwdRepository",
    "DwsRepository",
    "ReportRepository",
    "ReportStorage",
    "ReportBuilder",
]
