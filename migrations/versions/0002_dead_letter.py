"""新增死信表（M0 失败收口：重试耗尽/不可重试任务不静默丢弃）。

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-25

说明：0001 是基于 metadata 的基线，新建库会自动包含 dead_letter；
本迁移只对「已停在 0001 的既有库」做条件补表，避免重复建表。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _exists(bind: sa.engine.Connection) -> bool:
    return "dead_letter" in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _exists(bind):
        return
    op.create_table(
        "dead_letter",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("node_id", sa.String(length=16), nullable=True),
        sa.Column("err_code", sa.String(length=8), nullable=False),
        sa.Column("err_layer", sa.String(length=8), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_dead_letter_run_id", "dead_letter", ["run_id"])
    op.create_index("ix_dead_letter_err_code", "dead_letter", ["err_code"])
    op.create_index("ix_dead_letter_status", "dead_letter", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if _exists(bind):
        op.drop_table("dead_letter")
