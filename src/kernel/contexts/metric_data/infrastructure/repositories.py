"""数据中枢仓储：口径、ODS/DWD/DWS、报表。"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import func, select

from kernel.contexts.metric_data.domain.canonical_record import CanonicalRecord
from kernel.contexts.metric_data.domain.metric_definition import MetricDefinition, MetricValue
from kernel.contexts.metric_data.domain.review_ticket import ReviewTicket, TicketStatus
from kernel.contexts.metric_data.domain.stock import StockDiff, StockSuggestion
from kernel.contexts.metric_data.domain.ports import (
    DwdRepository,
    DwdWriteResult,
    DwsRepository,
    DailyFacts,
    MetricRepository,
    OdsRepository,
    RawPayload,
    AdCampaignRepository,
    MetricReleaseRepository,
    ReportRepository,
    SettlementRepository,
    ReviewTicketRepository,
    StockRepository,
)
from kernel.contexts.metric_data.domain.report import Report
from kernel.persistence.base import Database, as_utc, iso_or_none, utcnow
from kernel.persistence.tables import (
    AdCampaignMetricRow,
    DwdAd,
    DwdInventory,
    DwdOrder,
    DwdReview,
    DwdSettlementRow,
    DwdTraffic,
    DwsDailyMetric,
    MetricCardRow,
    MetricDefinitionRow,
    MetricReleaseRow,
    OdsRawPayload,
    ReportRow,
    ReviewTicketRow,
    SettlementDiffRow,
    StockDiffRow,
    StockSuggestionRow,
)
from shared.run_id import RunId
from shared.types.values import Additivity, Channel, NullReason, StatWindow


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


class SqlMetricRepository(MetricRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def definitions(self, platform: str) -> list[MetricDefinition]:
        with self.db.session() as session:
            rows = session.execute(
                select(MetricDefinitionRow)
                .where(MetricDefinitionRow.platform.in_([platform, "*"]))
                .order_by(MetricDefinitionRow.display_order, MetricDefinitionRow.id)
            ).scalars().all()
            return [self._to_domain(row) for row in rows]

    def definition(self, metric_code: str, version: str | None = None) -> MetricDefinition | None:
        with self.db.session() as session:
            statement = select(MetricDefinitionRow).where(
                MetricDefinitionRow.metric_code == metric_code
            )
            if version:
                statement = statement.where(MetricDefinitionRow.version == version)
            statement = statement.order_by(MetricDefinitionRow.id.desc()).limit(1)
            row = session.execute(statement).scalar_one_or_none()
            return self._to_domain(row) if row else None

    def upsert_definition(
        self, definition: MetricDefinition, card_payload: dict[str, Any]
    ) -> None:
        with self.db.session() as session:
            row = session.execute(
                select(MetricDefinitionRow).where(
                    MetricDefinitionRow.metric_code == definition.metric_code,
                    MetricDefinitionRow.version == definition.version,
                )
            ).scalar_one_or_none()
            if row is None:
                row = MetricDefinitionRow(
                    metric_code=definition.metric_code, version=definition.version
                )
                session.add(row)
            row.display_name = definition.display_name
            row.display_order = definition.display_order
            row.unit = definition.unit
            row.precision = definition.precision
            row.additivity = definition.additivity.value
            row.formula = definition.formula
            row.denominator = definition.denominator
            row.null_policy = definition.null_policy.name
            row.platform = definition.platform
            row.source_mapping = definition.source_mapping
            row.description = definition.description
            row.concept_uri = definition.concept_uri
            row.synonyms = list(definition.synonyms)
            row.probe_sql_template = definition.probe_sql_template
            row.quality_tests = list(definition.quality_tests)
            row.effective_from = definition.effective_from
            row.breaking_change = definition.breaking_change

            card = session.get(MetricCardRow, (definition.metric_code, definition.version))
            if card is None:
                card = MetricCardRow(
                    metric_code=definition.metric_code, version=definition.version
                )
                session.add(card)
            card.payload = card_payload
            card.status = "RELEASED"
            card.release_gate_passed = True
            card.released_at = utcnow()

    def cards(self) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(MetricCardRow).order_by(MetricCardRow.metric_code)
            ).scalars().all()
            return [
                {
                    "metric_code": row.metric_code,
                    "version": row.version,
                    "status": row.status,
                    "release_gate_passed": row.release_gate_passed,
                    "released_at": iso_or_none(row.released_at),
                    "card": row.payload,
                }
                for row in rows
            ]

    @staticmethod
    def _to_domain(row: MetricDefinitionRow) -> MetricDefinition:
        try:
            null_policy = NullReason[row.null_policy]
        except KeyError:
            null_policy = NullReason.NOT_APPLICABLE
        return MetricDefinition(
            metric_code=row.metric_code,
            display_name=row.display_name,
            version=row.version,
            unit=row.unit,
            precision=row.precision,
            additivity=Additivity(row.additivity),
            formula=row.formula,
            null_policy=null_policy,
            denominator=row.denominator,
            platform=row.platform,
            source_mapping=row.source_mapping,
            description=row.description,
            concept_uri=row.concept_uri,
            synonyms=tuple(row.synonyms or []),
            probe_sql_template=row.probe_sql_template,
            quality_tests=tuple(row.quality_tests or []),
            display_order=row.display_order,
            effective_from=row.effective_from,
            breaking_change=row.breaking_change,
        )


class SqlOdsRepository(OdsRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def save(self, run_id: RunId, raw: RawPayload) -> str:
        records = json.loads(json.dumps(raw.records, ensure_ascii=False, default=str))
        digest = raw.payload_hash or hashlib.sha256(
            json.dumps(raw.records, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()
        with self.db.session() as session:
            row = OdsRawPayload(
                run_id=run_id.value,
                platform=raw.platform,
                shop_id=raw.shop_id,
                channel=raw.channel.value,
                dataset=raw.dataset,
                payload_hash=digest,
                storage_ref=raw.storage_ref,
                payload={"records": records, "meta": raw.meta},
                record_count=len(records),
                fetched_at=utcnow(),
            )
            session.add(row)
            session.flush()
            return str(row.id)

    def by_run(self, run_id: RunId) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(OdsRawPayload)
                .where(OdsRawPayload.run_id == run_id.value)
                .order_by(OdsRawPayload.id)
            ).scalars().all()
            return [self._dict(row) for row in rows]

    def get(self, payload_id: int) -> dict[str, Any] | None:
        with self.db.session() as session:
            row = session.get(OdsRawPayload, payload_id)
            return self._dict(row) if row else None

    @staticmethod
    def _dict(row: OdsRawPayload) -> dict[str, Any]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "platform": row.platform,
            "shop_id": row.shop_id,
            "channel": row.channel,
            "dataset": row.dataset,
            "payload_hash": row.payload_hash,
            "storage_ref": row.storage_ref,
            "record_count": row.record_count,
            "payload": row.payload,
            "fetched_at": iso_or_none(row.fetched_at),
        }


class SqlDwdRepository(DwdRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def save_records(
        self, run_id: RunId, records: Sequence[CanonicalRecord]
    ) -> DwdWriteResult:
        result = DwdWriteResult()
        with self.db.session() as session:
            for record in records:
                dataset = record.dataset
                result.datasets[dataset] = result.datasets.get(dataset, 0)
                if dataset == "order":
                    exists = session.execute(
                        select(DwdOrder.id).where(
                            DwdOrder.platform == record.platform,
                            DwdOrder.shop_id == record.shop_id,
                            DwdOrder.order_id == str(record.value("order_id", "")),
                        )
                    ).scalar_one_or_none()
                    if exists:
                        result.skipped += 1
                        continue
                    session.add(
                        DwdOrder(
                            run_id=run_id.value,
                            platform=record.platform,
                            shop_id=record.shop_id,
                            stat_date=date.fromisoformat(str(record.value("stat_date"))),
                            order_id=str(record.value("order_id", "")),
                            paid_amount=_decimal(record.value("paid_amount", 0)) or Decimal(0),
                            refund_amount=_decimal(record.value("refund_amount", 0)) or Decimal(0),
                            status=str(record.value("status", "PAID")),
                            buyer_nickname=str(record.value("buyer_nickname", "")),
                            sku=str(record.value("sku", "")),
                        )
                    )
                elif dataset == "traffic":
                    day = date.fromisoformat(str(record.value("stat_date")))
                    exists = session.execute(
                        select(DwdTraffic.id).where(
                            DwdTraffic.platform == record.platform,
                            DwdTraffic.shop_id == record.shop_id,
                            DwdTraffic.stat_date == day,
                        )
                    ).scalar_one_or_none()
                    if exists:
                        result.skipped += 1
                        continue
                    session.add(
                        DwdTraffic(
                            run_id=run_id.value,
                            platform=record.platform,
                            shop_id=record.shop_id,
                            stat_date=day,
                            uv=int(record.value("uv", 0) or 0),
                            pv=int(record.value("pv", 0) or 0),
                        )
                    )
                elif dataset == "ad":
                    day = date.fromisoformat(str(record.value("stat_date")))
                    session.add(
                        DwdAd(
                            run_id=run_id.value,
                            platform=record.platform,
                            shop_id=record.shop_id,
                            stat_date=day,
                            campaign=str(record.value("campaign", "")),
                            cost=_decimal(record.value("cost", 0)) or Decimal(0),
                            attributed_revenue=_decimal(
                                record.value("attributed_revenue", 0)
                            )
                            or Decimal(0),
                        )
                    )
                elif dataset == "review":
                    review_id = str(record.value("review_id", ""))
                    exists = session.execute(
                        select(DwdReview.id).where(
                            DwdReview.platform == record.platform,
                            DwdReview.review_id == review_id,
                        )
                    ).scalar_one_or_none()
                    if exists:
                        result.skipped += 1
                        continue
                    review_day_raw = record.value("stat_date")
                    session.add(
                        DwdReview(
                            run_id=run_id.value,
                            platform=record.platform,
                            shop_id=record.shop_id,
                            review_id=review_id,
                            stat_date=date.fromisoformat(str(review_day_raw))
                            if review_day_raw
                            else None,
                            rating=int(record.value("rating", 5) or 5),
                            dsr=_decimal(record.value("dsr")) if record.value("dsr") else None,
                            content=str(record.value("content", "")),
                        )
                    )
                elif dataset == "settlement":
                    order_id = str(record.value("order_id", ""))
                    exists = session.execute(
                        select(DwdSettlementRow.id).where(
                            DwdSettlementRow.platform == record.platform,
                            DwdSettlementRow.order_id == order_id,
                        )
                    ).scalar_one_or_none()
                    if exists:
                        result.skipped += 1
                        continue
                    settled_raw = record.value("settlement_date")
                    settled_at = None
                    if settled_raw:
                        try:
                            parsed = datetime.fromisoformat(str(settled_raw))
                            settled_at = parsed
                        except ValueError:
                            settled_at = None
                    session.add(
                        DwdSettlementRow(
                            run_id=run_id.value,
                            platform=record.platform,
                            shop_id=record.shop_id,
                            order_id=order_id,
                            settlement_no=str(record.value("settlement_no", "")),
                            settlement_amount=_decimal(record.value("settlement_amount", 0))
                            or Decimal(0),
                            commission=_decimal(record.value("commission", 0)) or Decimal(0),
                            settled_at=settled_at,
                        )
                    )
                elif dataset == "inventory":
                    session.add(
                        DwdInventory(
                            run_id=run_id.value,
                            platform=record.platform,
                            shop_id=record.shop_id,
                            sku=str(record.value("sku", "")),
                            available=int(record.value("available", 0) or 0),
                            snapshot_at=utcnow(),
                        )
                    )
                else:
                    result.skipped += 1
                    continue
                result.saved += 1
                result.datasets[dataset] += 1
        return result

    def review_trend(
        self, platform: str, shop_id: str, limit: int = 14
    ) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(
                    DwdReview.stat_date,
                    func.avg(DwdReview.dsr),
                    func.count(DwdReview.id),
                )
                .where(
                    DwdReview.platform == platform,
                    DwdReview.shop_id == shop_id,
                    DwdReview.stat_date.is_not(None),
                )
                .group_by(DwdReview.stat_date)
                .order_by(DwdReview.stat_date.asc())
                .limit(limit)
            ).all()
            return [
                {
                    "stat_date": day.isoformat() if hasattr(day, "isoformat") else str(day),
                    "dsr": float(avg) if avg is not None else None,
                    "count": int(count or 0),
                }
                for day, avg, count in rows
            ]

    def facts(self, platform: str, shop_id: str, window: StatWindow) -> list[DailyFacts]:
        days = [
            window.start + timedelta(days=offset)
            for offset in range((window.end - window.start).days + 1)
        ]
        aggregates: dict[date, dict[str, Any]] = {day: {} for day in days}
        with self.db.session() as session:
            order_rows = session.execute(
                select(
                    DwdOrder.stat_date,
                    func.count(DwdOrder.id),
                    func.sum(DwdOrder.paid_amount),
                    func.sum(DwdOrder.refund_amount),
                )
                .where(
                    DwdOrder.platform == platform,
                    DwdOrder.shop_id == shop_id,
                    DwdOrder.stat_date >= window.start,
                    DwdOrder.stat_date <= window.end,
                )
                .group_by(DwdOrder.stat_date)
            ).all()
            for day, count, paid, refund in order_rows:
                aggregates.setdefault(day, {}).update(
                    {
                        "paid_orders": int(count or 0),
                        "gmv": paid or 0,
                        "refund_amount": refund or 0,
                    }
                )

            traffic_rows = session.execute(
                select(DwdTraffic.stat_date, DwdTraffic.uv, DwdTraffic.pv)
                .where(
                    DwdTraffic.platform == platform,
                    DwdTraffic.shop_id == shop_id,
                    DwdTraffic.stat_date >= window.start,
                    DwdTraffic.stat_date <= window.end,
                )
            ).all()
            for day, uv, pv in traffic_rows:
                aggregates.setdefault(day, {}).update({"uv": uv, "pv": pv})

            ad_rows = session.execute(
                select(
                    DwdAd.stat_date, func.sum(DwdAd.cost), func.sum(DwdAd.attributed_revenue)
                )
                .where(
                    DwdAd.platform == platform,
                    DwdAd.shop_id == shop_id,
                    DwdAd.stat_date >= window.start,
                    DwdAd.stat_date <= window.end,
                )
                .group_by(DwdAd.stat_date)
            ).all()
            for day, cost, revenue in ad_rows:
                aggregates.setdefault(day, {}).update(
                    {"ad_cost": cost or 0, "attributed_revenue": revenue or 0}
                )

            review_rows = session.execute(
                select(DwdReview.platform, func.avg(DwdReview.dsr))
                .where(DwdReview.platform == platform, DwdReview.shop_id == shop_id)
                .group_by(DwdReview.platform)
            ).all()
            dsr = review_rows[0][1] if review_rows else None

        results: list[DailyFacts] = []
        for day in days:
            facts = dict(aggregates.get(day) or {})
            if not facts:
                continue
            missing: dict[str, NullReason] = {}
            if "dsr" not in facts:
                facts["dsr"] = dsr
            if facts.get("dsr") is None:
                missing["dsr"] = NullReason.UNAUTHORIZED
            facts.setdefault("inventory_turnover", None)
            missing["inventory_turnover"] = NullReason.NOT_SUPPORTED
            for key in ("uv", "pv"):
                if key not in facts:
                    facts[key] = None
                    missing[key] = NullReason.NO_DATA
            results.append(DailyFacts(stat_date=day, facts=facts, missing_reasons=missing))
        return results


class SqlDwsRepository(DwsRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def save(
        self,
        run_id: RunId,
        platform: str,
        shop_id: str,
        stat_date: date,
        values: Sequence[MetricValue],
        channel: Channel,
    ) -> int:
        with self.db.session() as session:
            session.query(DwsDailyMetric).filter(
                DwsDailyMetric.run_id == run_id.value,
                DwsDailyMetric.stat_date == stat_date,
            ).delete()
            for value in values:
                session.add(
                    DwsDailyMetric(
                        run_id=run_id.value,
                        platform=platform,
                        shop_id=shop_id,
                        stat_date=stat_date,
                        metric_code=value.metric_code,
                        metric_version=value.metric_version,
                        value=value.value,
                        unit=value.unit,
                        precision=value.precision,
                        additivity=value.additivity.value,
                        null_reason=value.null_reason.value if value.null_reason else None,
                        channel=channel.value,
                        computed_at=utcnow(),
                    )
                )
            return len(values)

    def by_run(self, run_id: RunId) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(DwsDailyMetric)
                .where(DwsDailyMetric.run_id == run_id.value)
                .order_by(DwsDailyMetric.stat_date, DwsDailyMetric.metric_code)
            ).scalars().all()
            return [
                {
                    "stat_date": row.stat_date,
                    "metric_code": row.metric_code,
                    "metric_version": row.metric_version,
                    "value": row.value,
                    "unit": row.unit,
                    "precision": row.precision,
                    "additivity": row.additivity,
                    "null_reason": row.null_reason,
                    "channel": row.channel,
                }
                for row in rows
            ]


class SqlReportRepository(ReportRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def add(self, report: Report) -> None:
        with self.db.session() as session:
            session.add(
                ReportRow(
                    report_id=report.report_id,
                    run_id=report.run_id.value,
                    platform=report.platform,
                    shop_id=report.shop_id,
                    window_start=report.window.start,
                    window_end=report.window.end,
                    metric_version=report.metric_version,
                    artifact_ref=report.artifact_ref,
                    watermark=report.watermark,
                    status=report.status,
                    subscribers=[],
                    generated_at=report.generated_at,
                )
            )

    def get(self, report_id: str) -> Report | None:
        with self.db.session() as session:
            row = session.get(ReportRow, report_id)
            return self._to_domain(row) if row else None

    def recent(self, limit: int = 20) -> list[Report]:
        with self.db.session() as session:
            rows = session.execute(
                select(ReportRow).order_by(ReportRow.generated_at.desc()).limit(limit)
            ).scalars().all()
            return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: ReportRow) -> Report:
        return Report(
            report_id=row.report_id,
            run_id=RunId.parse(row.run_id),
            platform=row.platform,
            shop_id=row.shop_id,
            window=StatWindow(row.window_start, row.window_end),
            metric_version=row.metric_version,
            artifact_ref=row.artifact_ref,
            watermark=row.watermark,
            status=row.status,
            channel=Channel.BACKEND_EXPORT,
            generated_at=as_utc(row.generated_at) or utcnow(),
        )


class SqlReviewTicketRepository(ReviewTicketRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def exists(self, platform: str, review_id: str) -> bool:
        with self.db.session() as session:
            return (
                session.execute(
                    select(ReviewTicketRow.id).where(
                        ReviewTicketRow.platform == platform,
                        ReviewTicketRow.review_id == review_id,
                    )
                ).first()
                is not None
            )

    def add(self, ticket: ReviewTicket) -> None:
        with self.db.session() as session:
            session.add(self._to_row(ticket))

    def save(self, ticket: ReviewTicket) -> None:
        with self.db.session() as session:
            row = session.execute(
                select(ReviewTicketRow).where(ReviewTicketRow.ticket_id == ticket.ticket_id)
            ).scalar_one_or_none()
            if row is None:
                session.add(self._to_row(ticket))
                return
            row.status = ticket.status.value
            row.assignee = ticket.assignee
            row.closed_at = ticket.closed_at
            row.resolution = ticket.resolution

    def get(self, ticket_id: str) -> ReviewTicket | None:
        with self.db.session() as session:
            row = session.execute(
                select(ReviewTicketRow).where(ReviewTicketRow.ticket_id == ticket_id)
            ).scalar_one_or_none()
            return self._to_domain(row) if row else None

    def list(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.session() as session:
            statement = select(ReviewTicketRow).order_by(ReviewTicketRow.sla_due_at.asc())
            if status:
                statement = statement.where(ReviewTicketRow.status == status)
            rows = session.execute(statement.limit(limit)).scalars().all()
            return [self._dict(row) for row in rows]

    @staticmethod
    def _to_row(ticket: ReviewTicket) -> ReviewTicketRow:
        return ReviewTicketRow(
            ticket_id=ticket.ticket_id,
            run_id=ticket.run_id,
            platform=ticket.platform,
            shop_id=ticket.shop_id,
            review_id=ticket.review_id,
            sku=ticket.sku,
            rating=ticket.rating,
            dsr=ticket.dsr,
            content_masked=ticket.content_masked,
            hit_rule=ticket.hit_rule,
            severity=ticket.severity.value,
            status=ticket.status.value,
            assignee=ticket.assignee,
            sla_due_at=ticket.sla_due_at,
            evidence_ref=ticket.evidence_ref,
        )

    @staticmethod
    def _to_domain(row: ReviewTicketRow) -> ReviewTicket:
        from kernel.contexts.metric_data.domain.review_ticket import Severity

        return ReviewTicket(
            ticket_id=row.ticket_id,
            run_id=row.run_id,
            platform=row.platform,
            shop_id=row.shop_id,
            review_id=row.review_id,
            sku=row.sku,
            rating=row.rating,
            dsr=float(row.dsr) if row.dsr is not None else None,
            content_masked=row.content_masked,
            hit_rule=row.hit_rule,
            severity=Severity(row.severity),
            sla_due_at=as_utc(row.sla_due_at) or utcnow(),
            status=TicketStatus(row.status),
            assignee=row.assignee,
            closed_at=as_utc(row.closed_at),
            resolution=row.resolution,
            evidence_ref=row.evidence_ref,
        )

    @staticmethod
    def _dict(row: ReviewTicketRow) -> dict[str, Any]:
        return {
            "ticket_id": row.ticket_id,
            "run_id": row.run_id,
            "platform": row.platform,
            "shop_id": row.shop_id,
            "review_id": row.review_id,
            "sku": row.sku,
            "rating": row.rating,
            "dsr": float(row.dsr) if row.dsr is not None else None,
            "content_masked": row.content_masked,
            "hit_rule": row.hit_rule,
            "severity": row.severity,
            "status": row.status,
            "assignee": row.assignee,
            "sla_due_at": iso_or_none(row.sla_due_at),
            "created_at": iso_or_none(row.created_at),
            "closed_at": iso_or_none(row.closed_at),
            "resolution": row.resolution,
            "evidence_ref": row.evidence_ref,
        }


class SqlStockRepository(StockRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def save(
        self,
        run_id: RunId,
        platform: str,
        shop_id: str,
        diffs: Sequence[StockDiff],
        suggestions: Sequence[StockSuggestion],
    ) -> tuple[int, int]:
        with self.db.session() as session:
            session.query(StockDiffRow).filter(StockDiffRow.run_id == run_id.value).delete()
            for diff in diffs:
                session.add(
                    StockDiffRow(
                        run_id=run_id.value,
                        platform=platform,
                        shop_id=shop_id,
                        sku=diff.sku,
                        platform_available=diff.platform.available,
                        erp_available=diff.erp.available,
                        wms_available=diff.wms.available,
                        platform_snapshot_at=diff.platform.snapshot_at,
                        erp_snapshot_at=diff.erp.snapshot_at,
                        wms_snapshot_at=diff.wms.snapshot_at,
                        diff_type=diff.diff_type.value,
                        delta=diff.delta,
                        tolerance=diff.tolerance,
                    )
                )
            for suggestion in suggestions:
                session.add(
                    StockSuggestionRow(
                        suggestion_id=suggestion.suggestion_id,
                        run_id=run_id.value,
                        sku=suggestion.sku,
                        action=suggestion.action.value,
                        quantity=suggestion.quantity,
                        reason=suggestion.reason,
                        status=suggestion.status,
                    )
                )
            return len(diffs), len(suggestions)

    def by_run(self, run_id: RunId) -> dict[str, Any]:
        with self.db.session() as session:
            diffs = session.execute(
                select(StockDiffRow)
                .where(StockDiffRow.run_id == run_id.value)
                .order_by(StockDiffRow.sku)
            ).scalars().all()
            suggestions = session.execute(
                select(StockSuggestionRow)
                .where(StockSuggestionRow.run_id == run_id.value)
                .order_by(StockSuggestionRow.id)
            ).scalars().all()
            return {
                "diffs": [self._diff_dict(row) for row in diffs],
                "suggestions": [self._suggestion_dict(row) for row in suggestions],
            }

    def suggestions(
        self, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self.db.session() as session:
            statement = select(StockSuggestionRow).order_by(StockSuggestionRow.id.desc())
            if status:
                statement = statement.where(StockSuggestionRow.status == status)
            rows = session.execute(statement.limit(limit)).scalars().all()
            return [self._suggestion_dict(row) for row in rows]

    def resolve_suggestion(self, suggestion_id: str, status: str) -> bool:
        if status not in {"ACCEPTED", "IGNORED"}:
            raise ValueError("建议状态只能是 ACCEPTED / IGNORED")
        with self.db.session() as session:
            row = session.execute(
                select(StockSuggestionRow).where(
                    StockSuggestionRow.suggestion_id == suggestion_id
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            row.status = status
            row.resolved_at = utcnow()
            return True

    @staticmethod
    def _diff_dict(row: StockDiffRow) -> dict[str, Any]:
        return {
            "run_id": row.run_id,
            "sku": row.sku,
            "platform_available": row.platform_available,
            "erp_available": row.erp_available,
            "wms_available": row.wms_available,
            "platform_snapshot_at": iso_or_none(row.platform_snapshot_at),
            "erp_snapshot_at": iso_or_none(row.erp_snapshot_at),
            "wms_snapshot_at": iso_or_none(row.wms_snapshot_at),
            "diff_type": row.diff_type,
            "delta": row.delta,
            "tolerance": row.tolerance,
        }

    @staticmethod
    def _suggestion_dict(row: StockSuggestionRow) -> dict[str, Any]:
        return {
            "suggestion_id": row.suggestion_id,
            "run_id": row.run_id,
            "sku": row.sku,
            "action": row.action,
            "quantity": row.quantity,
            "reason": row.reason,
            "status": row.status,
            "created_at": iso_or_none(row.created_at),
            "resolved_at": iso_or_none(row.resolved_at),
        }


class SqlMetricReleaseRepository(MetricReleaseRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def add(self, result: Any) -> None:
        with self.db.session() as session:
            session.add(
                MetricReleaseRow(
                    metric_code=result.metric_code,
                    version=result.version,
                    gate_passed=result.passed,
                    checks=[check.to_dict() for check in result.checks],
                    checked_by=result.checked_by,
                    checked_at=result.checked_at,
                )
            )

    def latest(self, metric_code: str, version: str | None = None) -> dict[str, Any] | None:
        with self.db.session() as session:
            statement = select(MetricReleaseRow).where(
                MetricReleaseRow.metric_code == metric_code
            )
            if version:
                statement = statement.where(MetricReleaseRow.version == version)
            row = session.execute(
                statement.order_by(MetricReleaseRow.checked_at.desc()).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return {
                "metric_code": row.metric_code,
                "version": row.version,
                "gate_passed": row.gate_passed,
                "checks": row.checks,
                "checked_by": row.checked_by,
                "checked_at": iso_or_none(row.checked_at),
            }


class SqlAdCampaignRepository(AdCampaignRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def save(
        self,
        run_id: RunId,
        platform: str,
        shop_id: str,
        stat_date: Any,
        rows: Sequence[Any],
    ) -> int:
        with self.db.session() as session:
            session.query(AdCampaignMetricRow).filter(
                AdCampaignMetricRow.run_id == run_id.value
            ).delete()
            for row in rows:
                session.add(
                    AdCampaignMetricRow(
                        run_id=run_id.value,
                        platform=platform,
                        shop_id=shop_id,
                        stat_date=stat_date,
                        campaign=row["campaign"],
                        cost=row["cost"],
                        revenue=row["revenue"],
                        roi=row["roi"],
                        alert_level=row["alert_level"],
                        suggestion=row["suggestion"],
                    )
                )
            return len(rows)

    def by_run(self, run_id: RunId) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(AdCampaignMetricRow)
                .where(AdCampaignMetricRow.run_id == run_id.value)
                .order_by(AdCampaignMetricRow.cost.desc())
            ).scalars().all()
            return [
                {
                    "campaign": row.campaign,
                    "cost": float(row.cost) if row.cost is not None else 0.0,
                    "revenue": float(row.revenue) if row.revenue is not None else 0.0,
                    "roi": float(row.roi) if row.roi is not None else None,
                    "alert_level": row.alert_level,
                    "suggestion": row.suggestion,
                }
                for row in rows
            ]


class SqlSettlementRepository(SettlementRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def save(
        self, run_id: RunId, platform: str, shop_id: str, diffs: Sequence[Any]
    ) -> int:
        with self.db.session() as session:
            session.query(SettlementDiffRow).filter(
                SettlementDiffRow.run_id == run_id.value
            ).delete()
            for diff in diffs:
                session.add(
                    SettlementDiffRow(
                        run_id=run_id.value,
                        platform=platform,
                        shop_id=shop_id,
                        order_id=diff.order_id,
                        expected_net=diff.expected_net,
                        settled_amount=diff.settled_amount,
                        commission=diff.commission,
                        delta=diff.delta,
                        diff_type=diff.diff_type.value,
                        order_ref=diff.order_ref,
                        settlement_ref=diff.settlement_ref,
                    )
                )
            return len(diffs)

    def by_run(self, run_id: RunId) -> list[dict[str, Any]]:
        with self.db.session() as session:
            rows = session.execute(
                select(SettlementDiffRow)
                .where(SettlementDiffRow.run_id == run_id.value)
                .order_by(SettlementDiffRow.order_id)
            ).scalars().all()
            return [
                {
                    "order_id": row.order_id,
                    "expected_net": float(row.expected_net) if row.expected_net is not None else 0.0,
                    "settled_amount": float(row.settled_amount)
                    if row.settled_amount is not None
                    else None,
                    "commission": float(row.commission) if row.commission is not None else None,
                    "delta": float(row.delta) if row.delta is not None else 0.0,
                    "diff_type": row.diff_type,
                    "order_ref": row.order_ref,
                    "settlement_ref": row.settlement_ref,
                    "status": row.status,
                }
                for row in rows
            ]
