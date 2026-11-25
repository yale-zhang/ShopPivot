"""身份权限仓储。"""
from __future__ import annotations

from sqlalchemy import select

from kernel.contexts.identity.domain.account import (
    Account,
    AccountRepository,
    ApiTokenRepository,
    Role,
    ShopScope,
)
from kernel.contexts.identity.infrastructure.auth import hash_token
from kernel.persistence.base import Database
from kernel.persistence.tables import AccountRow, ApiTokenRow, ShopAuthorizationRow


class SqlAccountRepository(AccountRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def by_username(self, username: str) -> tuple[Account, str] | None:
        with self.db.session() as session:
            row = session.execute(
                select(AccountRow).where(AccountRow.username == username)
            ).scalar_one_or_none()
            if row is None or not row.enabled:
                return None
            return (
                Account(
                    id=row.id,
                    username=row.username,
                    display_name=row.display_name,
                    role=Role(row.role),
                    enabled=row.enabled,
                ),
                row.password_hash,
            )

    def add(self, username: str, display_name: str, password_hash: str, role: Role) -> Account:
        with self.db.session() as session:
            row = AccountRow(
                username=username,
                display_name=display_name,
                password_hash=password_hash,
                role=role.value,
                enabled=True,
            )
            session.add(row)
            session.flush()
            return Account(
                id=row.id,
                username=row.username,
                display_name=row.display_name,
                role=Role(row.role),
            )

    def shops(self, account_id: int) -> list[ShopScope]:
        with self.db.session() as session:
            rows = session.execute(
                select(ShopAuthorizationRow).where(
                    ShopAuthorizationRow.account_id == account_id
                )
            ).scalars().all()
            return [ShopScope(row.platform, row.shop_id) for row in rows]


class SqlApiTokenRepository(ApiTokenRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def register(self, name: str, token: str, scope: str) -> None:
        with self.db.session() as session:
            session.add(
                ApiTokenRow(name=name, token_hash=hash_token(token), scope=scope, enabled=True)
            )

    def resolve(self, token: str) -> str | None:
        with self.db.session() as session:
            row = session.execute(
                select(ApiTokenRow).where(ApiTokenRow.token_hash == hash_token(token))
            ).scalar_one_or_none()
            if row is None or not row.enabled:
                return None
            return row.scope
