"""P13 1688 选品与采购：sourcing_candidate / purchase_order。

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from kernel.persistence import tables  # noqa: F401
from kernel.persistence.base import Base

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_TABLES = ["sourcing_candidate", "purchase_order"]


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    pending = [
        table
        for table in Base.metadata.sorted_tables
        if table.name in _TABLES and table.name not in existing
    ]
    if pending:
        Base.metadata.create_all(bind, tables=pending)


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table in reversed([name for name in _TABLES if name in existing]):
        op.drop_table(table)
