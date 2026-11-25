"""物理数据层基座（Kernel 拥有的统一数据模型）。

- 生产用 PostgreSQL（JSONB、审计触发器）；
- 测试/本地默认 SQLite（JSON 变体），保证无 Docker 也能跑通集成与端到端测试；
- 所有 datetime 以 UTC 存储，读取时统一归一到 aware UTC。
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

JsonType = JSON().with_variant(JSONB(), "postgresql")  # type: ignore[no-untyped-call]


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_or_none(value: datetime | None) -> str | None:
    stamp = as_utc(value)
    return stamp.isoformat() if stamp else None


class Database:
    """轻量数据库门面：引擎 + 会话工厂 + 建表/删表。"""

    def __init__(self, url: str, echo: bool = False) -> None:
        self.url = url
        connect_args: dict[str, Any] = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            if ":memory:" not in url:
                Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            url, echo=echo, future=True, pool_pre_ping=True, connect_args=connect_args
        )
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._sqlite_pragmas)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    @staticmethod
    def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def create_all(self) -> None:
        from kernel.persistence import tables  # noqa: F401

        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
