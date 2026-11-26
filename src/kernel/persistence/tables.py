"""统一数据模型物理表（主文档表 8-11 / 表 3-7）。

分层约定：
- run / node / module / audit / outbox 属编排与治理；
- ods_* 原始层、dwd_* 明细层、dws_* 汇总层、report 属数据中枢；
- 审计与日志表只增不改（PostgreSQL 侧由迁移安装触发器）。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from kernel.persistence.base import Base, JsonType, utcnow


class RunInstance(Base):
    __tablename__ = "run_instance"

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    app_id: Mapped[str] = mapped_column(String(64), index=True)
    scene: Mapped[str] = mapped_column(String(8), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    window_start: Mapped[date] = mapped_column(Date)
    window_end: Mapped[date] = mapped_column(Date)
    trigger_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), index=True)
    gate_level_max: Mapped[str] = mapped_column(String(2), default="L0")
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    config_snapshot_hash: Mapped[str] = mapped_column(String(64), default="")
    requested_by: Mapped[str] = mapped_column(String(64), default="system")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    err_code: Mapped[str | None] = mapped_column(String(8))
    err_layer: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_run_status_started", "status", "started_at"),)


class NodeExecutionRow(Base):
    __tablename__ = "node_execution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("run_instance.run_id"))
    node_id: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    channel: Mapped[str | None] = mapped_column(String(24))
    cost_ms: Mapped[int] = mapped_column(Integer, default=0)
    err_code: Mapped[str | None] = mapped_column(String(8))
    err_layer: Mapped[str | None] = mapped_column(String(8))
    payload_digest: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("run_id", "node_id", name="uq_node_run_node"),)


class AppPackageRow(Base):
    __tablename__ = "app_package"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(16))
    scene: Mapped[str] = mapped_column(String(8))
    gate_level: Mapped[str] = mapped_column(String(2), default="L0")
    status: Mapped[str] = mapped_column(String(16), default="PUBLISHED")
    module: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("app_id", "version", name="uq_app_package_version"),)


class SchedulePlanRow(Base):
    __tablename__ = "schedule_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[str] = mapped_column(String(64), index=True)
    cron: Mapped[str] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    degrade_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class IdempotencyKeyRow(Base):
    __tablename__ = "idempotency_key"

    key: Mapped[str] = mapped_column(String(220), primary_key=True)
    scope: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(String(200))
    run_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboxEvent(Base):
    __tablename__ = "outbox_event"

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(32))
    aggregate_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class GatePolicyRow(Base):
    __tablename__ = "gate_policy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_code: Mapped[str] = mapped_column(String(64), index=True)
    gate_level: Mapped[str] = mapped_column(String(2))
    version: Mapped[str] = mapped_column(String(16), default="1")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signed_by: Mapped[str] = mapped_column(String(64), default="")
    module: Mapped[str] = mapped_column(String(64), default="")

    __table_args__ = (
        UniqueConstraint("action_code", "version", name="uq_gate_policy_version"),
    )


class ApprovalTaskRow(Base):
    __tablename__ = "approval_task"

    task_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    gate_level: Mapped[str] = mapped_column(String(2), default="L2")
    action_code: Mapped[str] = mapped_column(String(64), default="")
    scene: Mapped[str] = mapped_column(String(8), default="S01")
    platform: Mapped[str] = mapped_column(String(32), default="")
    shop_id: Mapped[str] = mapped_column(String(64), default="")
    write_plan: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    write_plan_hash: Mapped[str] = mapped_column(String(64), default="")
    impact_scope: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    sla_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    change_order_no: Mapped[str | None] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(64), default="system")
    approver: Mapped[str] = mapped_column(String(64), default="owner")
    reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(220), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ApprovalEvidenceRow(Base):
    __tablename__ = "approval_evidence"

    task_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("approval_task.task_id"), primary_key=True
    )
    operator: Mapped[str] = mapped_column(String(64))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    change_order_no: Mapped[str] = mapped_column(String(64))
    before_shot: Mapped[str] = mapped_column(String(255))
    after_shot: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(64))


class ChangeOrderRow(Base):
    __tablename__ = "change_order"

    change_order_no: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    after_snapshot: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    rollback_plan: Mapped[str | None] = mapped_column(Text)
    evidence_ref: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MetricDefinitionRow(Base):
    __tablename__ = "metric_definition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_code: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(16))
    display_name: Mapped[str] = mapped_column(String(64))
    display_order: Mapped[int] = mapped_column(Integer, default=100)
    unit: Mapped[str] = mapped_column(String(16), default="")
    precision: Mapped[int] = mapped_column(Integer, default=0)
    additivity: Mapped[str] = mapped_column(String(16), default="ADDITIVE")
    formula: Mapped[str] = mapped_column(Text, default="0")
    denominator: Mapped[str | None] = mapped_column(Text)
    null_policy: Mapped[str] = mapped_column(String(24), default="NOT_APPLICABLE")
    platform: Mapped[str] = mapped_column(String(32), default="demo")
    source_mapping: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    concept_uri: Mapped[str] = mapped_column(String(128), default="")
    synonyms: Mapped[list[str]] = mapped_column(JsonType, default=list)
    probe_sql_template: Mapped[str] = mapped_column(Text, default="")
    quality_tests: Mapped[list[str]] = mapped_column(JsonType, default=list)
    effective_from: Mapped[str] = mapped_column(String(32), default="")
    breaking_change: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("metric_code", "version", name="uq_metric_code_version"),
    )


class MetricCardRow(Base):
    __tablename__ = "metric_card"

    metric_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(16), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="RELEASED")
    release_gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    released_by: Mapped[str] = mapped_column(String(64), default="system")
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OdsRawPayload(Base):
    __tablename__ = "ods_raw_payload"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(24))
    dataset: Mapped[str] = mapped_column(String(64), default="")
    payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    storage_ref: Mapped[str] = mapped_column(String(255), default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DwdOrder(Base):
    __tablename__ = "dwd_order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    stat_date: Mapped[date] = mapped_column(Date, index=True)
    order_id: Mapped[str] = mapped_column(String(64))
    paid_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    refund_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(24), default="PAID")
    buyer_nickname: Mapped[str] = mapped_column(String(64), default="")
    sku: Mapped[str] = mapped_column(String(64), default="")

    __table_args__ = (
        UniqueConstraint("platform", "shop_id", "order_id", name="uq_dwd_order_business"),
        Index("ix_dwd_order_shop_date", "platform", "shop_id", "stat_date"),
    )


class DwdTraffic(Base):
    __tablename__ = "dwd_traffic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    stat_date: Mapped[date] = mapped_column(Date, index=True)
    uv: Mapped[int] = mapped_column(Integer, default=0)
    pv: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("platform", "shop_id", "stat_date", name="uq_dwd_traffic_day"),
    )


class DwdAd(Base):
    __tablename__ = "dwd_ad"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    stat_date: Mapped[date] = mapped_column(Date, index=True)
    campaign: Mapped[str] = mapped_column(String(64), default="")
    cost: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    attributed_revenue: Mapped[float] = mapped_column(Numeric(18, 2), default=0)


class DwdReview(Base):
    __tablename__ = "dwd_review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    review_id: Mapped[str] = mapped_column(String(64))
    stat_date: Mapped[date | None] = mapped_column(Date)
    rating: Mapped[int] = mapped_column(Integer, default=5)
    dsr: Mapped[float | None] = mapped_column(Numeric(4, 2))
    content: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        UniqueConstraint("platform", "review_id", name="uq_dwd_review_id"),
        Index("ix_dwd_review_shop_date", "platform", "shop_id", "stat_date"),
    )


class DwdInventory(Base):
    __tablename__ = "dwd_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    sku: Mapped[str] = mapped_column(String(64))
    available: Mapped[int] = mapped_column(Integer, default=0)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DwsDailyMetric(Base):
    __tablename__ = "dws_daily_metric"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    stat_date: Mapped[date] = mapped_column(Date, index=True)
    metric_code: Mapped[str] = mapped_column(String(64), index=True)
    metric_version: Mapped[str] = mapped_column(String(16))
    value: Mapped[float | None] = mapped_column(Numeric(20, 6))
    unit: Mapped[str] = mapped_column(String(16), default="")
    precision: Mapped[int] = mapped_column(Integer, default=0)
    additivity: Mapped[str] = mapped_column(String(16), default="ADDITIVE")
    null_reason: Mapped[str | None] = mapped_column(String(24))
    channel: Mapped[str] = mapped_column(String(24), default="")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "run_id", "stat_date", "platform", "shop_id", "metric_code",
            name="uq_dws_metric_run_day",
        ),
    )


class ReportRow(Base):
    __tablename__ = "report"

    report_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    window_start: Mapped[date] = mapped_column(Date)
    window_end: Mapped[date] = mapped_column(Date)
    metric_version: Mapped[str] = mapped_column(String(64), default="")
    artifact_ref: Mapped[str] = mapped_column(String(255), default="")
    watermark: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="GENERATED")
    subscribers: Mapped[list[str]] = mapped_column(JsonType, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SkuMappingRow(Base):
    __tablename__ = "sku_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32))
    platform_sku: Mapped[str] = mapped_column(String(64))
    canonical_sku: Mapped[str] = mapped_column(String(64))
    strategy: Mapped[str] = mapped_column(String(24), default="EXACT")
    confidence: Mapped[float] = mapped_column(Numeric(4, 2), default=1)
    confirmed_by: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("platform", "platform_sku", name="uq_sku_mapping_platform"),
    )


class StatusEnumMappingRow(Base):
    __tablename__ = "status_enum_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32))
    platform_status: Mapped[str] = mapped_column(String(48))
    canonical_status: Mapped[str] = mapped_column(String(24))

    __table_args__ = (
        UniqueConstraint("platform", "platform_status", name="uq_status_enum_platform"),
    )


class DataSourceRow(Base):
    __tablename__ = "data_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(24))
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, default=0)
    credential_ref: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AdapterFieldMapRow(Base):
    __tablename__ = "adapter_field_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32))
    dataset: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(16), default="1")
    field_map: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    __table_args__ = (
        UniqueConstraint("platform", "dataset", "version", name="uq_field_map_version"),
    )


class DataContractRow(Base):
    __tablename__ = "data_contract"

    dataset: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(16), primary_key=True)
    schema_def: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    required_fields: Mapped[list[str]] = mapped_column(JsonType, default=list)
    enum_sets: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    quality_tests: Mapped[list[str]] = mapped_column(JsonType, default=list)
    platform: Mapped[str] = mapped_column(String(32), default="")


class NotificationLogRow(Base):
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String(16))
    receiver: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(24))
    dedupe_key: Mapped[str] = mapped_column(String(220), unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="SENT")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    receipt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CredentialRefRow(Base):
    __tablename__ = "credential_ref"

    ref: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(255), default="")
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkerRow(Base):
    __tablename__ = "worker"

    worker_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="ONLINE")
    capabilities: Mapped[list[str]] = mapped_column(JsonType, default=list)
    queue_depth: Mapped[int] = mapped_column(Integer, default=0)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkerHeartbeatRow(Base):
    __tablename__ = "worker_heartbeat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ONLINE")
    queue_depth: Mapped[int] = mapped_column(Integer, default=0)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), index=True)
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[str] = mapped_column(String(96), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    after: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    ip: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(16), default="OK")


class ExceptionRecordRow(Base):
    __tablename__ = "exception_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(32), index=True)
    node_id: Mapped[str | None] = mapped_column(String(16))
    err_code: Mapped[str] = mapped_column(String(8), index=True)
    err_layer: Mapped[str] = mapped_column(String(8), index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    screenshot_ref: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeadLetterRow(Base):
    __tablename__ = "dead_letter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    node_id: Mapped[str | None] = mapped_column(String(16))
    err_code: Mapped[str] = mapped_column(String(8), index=True)
    err_layer: Mapped[str] = mapped_column(String(8))
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModuleStateRow(Base):
    __tablename__ = "module_state"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    contributions: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    blocking_reason: Mapped[str | None] = mapped_column(Text)
    last_loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModuleLoadReportRow(Base):
    __tablename__ = "module_load_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    report: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class AccountRow(Base):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="VIEWER")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ShopAuthorizationRow(Base):
    __tablename__ = "shop_authorization"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"))
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16), default="VIEWER")

    __table_args__ = (
        UniqueConstraint("account_id", "platform", "shop_id", name="uq_shop_auth"),
    )


class ApiTokenRow(Base):
    __tablename__ = "api_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    scope: Mapped[str] = mapped_column(String(16), default="READONLY")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewTicketRow(Base):
    __tablename__ = "review_ticket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(40), unique=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    review_id: Mapped[str] = mapped_column(String(64))
    sku: Mapped[str] = mapped_column(String(64), default="")
    rating: Mapped[int] = mapped_column(Integer, default=5)
    dsr: Mapped[float | None] = mapped_column(Numeric(4, 2))
    content_masked: Mapped[str] = mapped_column(Text, default="")
    hit_rule: Mapped[str] = mapped_column(String(64), default="")
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    status: Mapped[str] = mapped_column(String(16), default="OPEN", index=True)
    assignee: Mapped[str | None] = mapped_column(String(64))
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)
    evidence_ref: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        UniqueConstraint("platform", "review_id", name="uq_review_ticket_source"),
        Index("ix_review_ticket_status_sla", "status", "sla_due_at"),
    )


class StockDiffRow(Base):
    __tablename__ = "stock_diff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    sku: Mapped[str] = mapped_column(String(64))
    platform_available: Mapped[int | None] = mapped_column(Integer)
    erp_available: Mapped[int | None] = mapped_column(Integer)
    wms_available: Mapped[int | None] = mapped_column(Integer)
    platform_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erp_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    wms_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    diff_type: Mapped[str] = mapped_column(String(24), index=True)
    delta: Mapped[int] = mapped_column(Integer, default=0)
    tolerance: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("run_id", "sku", name="uq_stock_diff_run_sku"),)


class StockSuggestionRow(Base):
    __tablename__ = "stock_suggestion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[str] = mapped_column(String(40), unique=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    sku: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(24))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MetricReleaseRow(Base):
    __tablename__ = "metric_release"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_code: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(16))
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    checked_by: Mapped[str] = mapped_column(String(64), default="system")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("metric_code", "version", "checked_at", name="uq_metric_release"),
    )


class SubscriptionRow(Base):
    __tablename__ = "subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(16), index=True)
    receiver: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(24), default="CONSOLE")
    window: Mapped[str] = mapped_column(String(32), default="昨日")
    thresholds: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    silent_window: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("event", "receiver", name="uq_subscription_event_receiver"),
    )


class N8nCommandLogRow(Base):
    __tablename__ = "n8n_command_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command: Mapped[str] = mapped_column(String(64), index=True)
    token_scope: Mapped[str] = mapped_column(String(16))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    run_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WritePlanRow(Base):
    __tablename__ = "write_plan"

    plan_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    action_code: Mapped[str] = mapped_column(String(64), index=True)
    scene: Mapped[str] = mapped_column(String(8), default="S02")
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), index=True)
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    impact_scope: Mapped[str] = mapped_column(Text, default="")
    rollback_plan: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    plan_hash: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(64), default="system")
    approval_task_id: Mapped[str | None] = mapped_column(String(40))
    execution_id: Mapped[str | None] = mapped_column(String(40))
    idempotency_key: Mapped[str] = mapped_column(String(220), unique=True)
    error_code: Mapped[str | None] = mapped_column(String(8))
    error_layer: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WriteExecutionRow(Base):
    __tablename__ = "write_execution"

    execution_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(40), index=True)
    task_id: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="RUNNING")
    applied_rows: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    before_shot: Mapped[str] = mapped_column(String(255), default="")
    after_shot: Mapped[str] = mapped_column(String(255), default="")
    verify_result: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    details: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    err_code: Mapped[str | None] = mapped_column(String(8))
    err_layer: Mapped[str | None] = mapped_column(String(8))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WriteTokenRow(Base):
    __tablename__ = "write_token"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(40), index=True)
    plan_id: Mapped[str] = mapped_column(String(40), index=True)
    issued_by: Mapped[str] = mapped_column(String(64), default="")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DwdSettlementRow(Base):
    __tablename__ = "dwd_settlement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    order_id: Mapped[str] = mapped_column(String(64))
    settlement_no: Mapped[str] = mapped_column(String(64), default="")
    settlement_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    commission: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("platform", "order_id", name="uq_dwd_settlement_order"),
        Index("ix_dwd_settlement_run", "run_id"),
    )


class SettlementDiffRow(Base):
    __tablename__ = "settlement_diff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    order_id: Mapped[str] = mapped_column(String(64))
    expected_net: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    settled_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    commission: Mapped[float | None] = mapped_column(Numeric(18, 2))
    delta: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    diff_type: Mapped[str] = mapped_column(String(24), index=True)
    order_ref: Mapped[str] = mapped_column(String(255), default="")
    settlement_ref: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("run_id", "order_id", name="uq_settlement_diff_run"),)


class SourcingCandidateRow(Base):
    __tablename__ = "sourcing_candidate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    keyword: Mapped[str] = mapped_column(String(128), default="")
    offer_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    post_fee: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    moq: Mapped[int] = mapped_column(Integer, default=1)
    sales_30d: Mapped[int] = mapped_column(Integer, default=0)
    supplier: Mapped[str] = mapped_column(String(128), default="")
    pic_url: Mapped[str] = mapped_column(String(512), default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    brand_authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    score: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    risk_flags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    raw: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("run_id", "offer_id", name="uq_sourcing_candidate_run"),
        Index("ix_sourcing_candidate_offer", "offer_id"),
    )


class PurchaseOrderRow(Base):
    __tablename__ = "purchase_order"

    plan_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), default="")
    items: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    total: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    checkout_id: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(24), default="AWAITING_PAYMENT", index=True)
    continue_url: Mapped[str] = mapped_column(String(1024), default="")
    buyer_note: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SkillInstallationRow(Base):
    __tablename__ = "skill_installation"

    skill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(16), default="INSTALLED", index=True)
    checksum: Mapped[str] = mapped_column(String(128), default="")
    manifest_path: Mapped[str] = mapped_column(String(512), default="")
    installed_by: Mapped[str] = mapped_column(String(64), default="owner")
    details: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SkillBindingRow(Base):
    __tablename__ = "skill_binding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(String(64), index=True)
    platform: Mapped[str] = mapped_column(String(32), default="*")
    shop_id: Mapped[str] = mapped_column(String(64), default="*")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=10)
    credential_ref: Mapped[str] = mapped_column(String(128), default="")
    config: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        UniqueConstraint("skill_id", "platform", "shop_id", name="uq_skill_binding_scope"),
    )


class SkillRunRow(Base):
    __tablename__ = "skill_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    skill_id: Mapped[str] = mapped_column(String(64), index=True)
    skill_version: Mapped[str] = mapped_column(String(32), default="")
    capability: Mapped[str] = mapped_column(String(64), index=True)
    scene: Mapped[str] = mapped_column(String(16), default="")
    platform: Mapped[str] = mapped_column(String(32), default="")
    shop_id: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="SUCCEEDED")
    input_digest: Mapped[str] = mapped_column(String(64), default="")
    output_digest: Mapped[str] = mapped_column(String(64), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdCampaignMetricRow(Base):
    __tablename__ = "ad_campaign_metric"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    shop_id: Mapped[str] = mapped_column(String(64))
    stat_date: Mapped[date] = mapped_column(Date)
    campaign: Mapped[str] = mapped_column(String(64))
    cost: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    revenue: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    roi: Mapped[float | None] = mapped_column(Numeric(12, 4))
    alert_level: Mapped[str] = mapped_column(String(16), default="OK")
    suggestion: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("run_id", "campaign", name="uq_ad_campaign_run"),)
