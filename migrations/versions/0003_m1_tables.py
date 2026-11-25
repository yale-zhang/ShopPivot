"""M1 表与 dwd_review.stat_date 补列。

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-25

0001 为 metadata 基线，新建库已包含 M1 表；本迁移只对既有库做条件补表/补列。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from kernel.persistence import tables  # noqa: F401  注册完整 metadata
from kernel.persistence.base import Base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_M1_TABLES = [
    "review_ticket",
    "stock_diff",
    "stock_suggestion",
    "metric_release",
    "subscription",
    "n8n_command_log",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "dwd_review" in table_names:
        columns = {column["name"] for column in inspector.get_columns("dwd_review")}
        if "stat_date" not in columns:
            op.add_column("dwd_review", sa.Column("stat_date", sa.Date(), nullable=True))
        indexes = {index["name"] for index in inspector.get_indexes("dwd_review")}
        if "ix_dwd_review_shop_date" not in indexes:
            op.create_index(
                "ix_dwd_review_shop_date", "dwd_review", ["platform", "shop_id", "stat_date"]
            )

    pending = [table for table in Base.metadata.sorted_tables if table.name in _M1_TABLES]
    missing = [table for table in pending if table.name not in table_names]
    if missing:
        Base.metadata.create_all(bind, tables=missing)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    for table in reversed([name for name in _M1_TABLES if name in table_names]):
        op.drop_table(table)
    if "dwd_review" in table_names:
        columns = {column["name"] for column in inspector.get_columns("dwd_review")}
        indexes = {index["name"] for index in inspector.get_indexes("dwd_review")}
        if "ix_dwd_review_shop_date" in indexes:
            op.drop_index("ix_dwd_review_shop_date", table_name="dwd_review")
        if "stat_date" in columns:
            with op.batch_alter_table("dwd_review") as batch:
                batch.drop_column("stat_date")
