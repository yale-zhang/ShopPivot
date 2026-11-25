"""S03/S04：审批转交人字段 + 投放计划汇总表。

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from kernel.persistence import tables  # noqa: F401
from kernel.persistence.base import Base

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_TABLES = ["ad_campaign_metric"]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    names = set(inspector.get_table_names())
    if "approval_task" in names:
        columns = {column["name"] for column in inspector.get_columns("approval_task")}
        if "approver" not in columns:
            op.add_column(
                "approval_task",
                sa.Column("approver", sa.String(length=64), nullable=False, server_default="owner"),
            )
    pending = [
        table
        for table in Base.metadata.sorted_tables
        if table.name in _TABLES and table.name not in names
    ]
    if pending:
        Base.metadata.create_all(bind, tables=pending)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    names = set(inspector.get_table_names())
    for table in reversed([name for name in _TABLES if name in names]):
        op.drop_table(table)
    if "approval_task" in names:
        columns = {column["name"] for column in inspector.get_columns("approval_task")}
        if "approver" in columns:
            with op.batch_alter_table("approval_task") as batch:
                batch.drop_column("approver")
