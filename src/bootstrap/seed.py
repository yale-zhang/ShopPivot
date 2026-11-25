"""初始化种子数据：账号、店铺授权、机器 token。

仅 dev 使用默认口令；非 dev 环境必须通过环境变量提供，否则拒绝启动种子。
"""
from __future__ import annotations

import os

from sqlalchemy import select

from bootstrap.container import AppContainer
from kernel.contexts.identity.domain.account import Role
from kernel.contexts.identity.infrastructure.auth import hash_password, new_api_token
from kernel.persistence.tables import ApiTokenRow, ShopAuthorizationRow

DEV_USERS = [
    ("owner", "工作室负责人", Role.OWNER, "owner123"),
    ("editor", "运营", Role.EDITOR, "editor123"),
    ("viewer", "只读", Role.VIEWER, "viewer123"),
]


def _password(username: str, fallback: str, env: str) -> str:
    key = f"SHOPPIVOT_{username.upper()}_PASSWORD"
    value = os.environ.get(key)
    if value:
        return value
    if env not in {"dev", "test"}:
        raise RuntimeError(f"非 dev 环境必须设置 {key}")
    return fallback


def seed_identity(container: AppContainer) -> dict[str, object]:
    created: list[str] = []
    for username, display, role, fallback in DEV_USERS:
        if container.accounts.by_username(username) is None:
            container.accounts.add(
                username,
                display,
                hash_password(_password(username, fallback, container.settings.env)),
                role,
            )
            created.append(username)

    with container.database.session() as session:
        for username, _, role, _ in DEV_USERS:
            account = container.accounts.by_username(username)
            if account is None:
                continue
            account_id = account[0].id
            exists = session.execute(
                select(ShopAuthorizationRow).where(
                    ShopAuthorizationRow.account_id == account_id,
                    ShopAuthorizationRow.platform == container.settings.platform,
                    ShopAuthorizationRow.shop_id == container.settings.shop_id,
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    ShopAuthorizationRow(
                        account_id=account_id,
                        platform=container.settings.platform_source
                        or container.settings.platform,
                        shop_id=container.settings.shop_id,
                        role=role.value,
                    )
                )

    machine_token: str | None = None
    with container.database.session() as session:
        row = session.execute(select(ApiTokenRow)).scalars().first()
        if row is None:
            machine_token = new_api_token()
            container.api_tokens.register("worker-headless", machine_token, "READONLY")
    if machine_token:
        path = container.settings.storage_dir / "worker.token"
        path.write_text(machine_token, encoding="utf-8")
        os.chmod(path, 0o600)
    return {
        "created_users": created,
        "machine_token_created": machine_token is not None,
        "machine_token_file": str(container.settings.storage_dir / "worker.token"),
    }


def seed_all(container: AppContainer) -> dict[str, object]:
    result = seed_identity(container)
    result["metric_cards"] = len(container.metrics.cards())
    result["modules_loaded"] = (
        container.startup_report.loaded if container.startup_report else []
    )
    return result
