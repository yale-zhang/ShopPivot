"""测试夹具：临时 SQLite + 临时对象存储 + 真实模块目录。"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bootstrap.api import create_app
from bootstrap.container import AppContainer, build_container, run_daily
from bootstrap.seed import seed_identity
from bootstrap.settings import Settings

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "modules"


@pytest.fixture(scope="session")
def modules_dir() -> Path:
    return MODULES_DIR


@pytest.fixture()
def settings(tmp_path: Path, modules_dir: Path) -> Settings:
    return Settings(
        env="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_dir=tmp_path / "storage",
        modules_dir=modules_dir,
        platform_source="demo",
        platform="demo",
        shop_id="SHOP-0001",
        jwt_secret="test-secret-32-bytes-minimum-value",
        allow_l2_simulation=True,
        platform_gate_max="L0",
    )


@pytest.fixture()
def container(settings: Settings) -> AppContainer:
    return build_container(settings)


@pytest.fixture()
def seeded(container: AppContainer) -> AppContainer:
    seed_identity(container)
    return container


@pytest.fixture()
def client(seeded: AppContainer) -> TestClient:
    app = create_app(seeded.settings, container=seeded)
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def owner_headers(client: TestClient) -> dict[str, str]:
    return _login(client, "owner", "owner123")


@pytest.fixture()
def viewer_headers(client: TestClient) -> dict[str, str]:
    return _login(client, "viewer", "viewer123")


@pytest.fixture()
def daily_run(seeded: AppContainer):
    # 固定统计日，fixture 的 {D0}/{D-1} 占位符按该窗口解析
    return run_daily(seeded, day="2026-11-25")


@pytest.fixture()
def m1_settings(tmp_path: Path, modules_dir: Path) -> Settings:
    return Settings(
        env="test",
        database_url=f"sqlite:///{tmp_path / 'm1.db'}",
        storage_dir=tmp_path / "m1_storage",
        modules_dir=modules_dir,
        platform_source="demo",
        platform="demo",
        shop_id="SHOP-0001",
        jwt_secret="test-secret-32-bytes-minimum-value",
        allow_l2_simulation=True,
        platform_gate_max="L1",
    )


@pytest.fixture()
def m1_container(m1_settings: Settings) -> AppContainer:
    return build_container(m1_settings)


@pytest.fixture()
def m1_seeded(m1_container: AppContainer) -> AppContainer:
    seed_identity(m1_container)
    return m1_container


@pytest.fixture()
def m1_client(m1_seeded: AppContainer) -> TestClient:
    app = create_app(m1_seeded.settings, container=m1_seeded)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def m1_headers(m1_client: TestClient) -> dict[str, str]:
    return _login(m1_client, "owner", "owner123")


@pytest.fixture()
def m2_settings(tmp_path: Path, modules_dir: Path) -> Settings:
    return Settings(
        env="test",
        database_url=f"sqlite:///{tmp_path / 'm2.db'}",
        storage_dir=tmp_path / "m2_storage",
        modules_dir=modules_dir,
        platform_source="demo",
        platform="demo",
        shop_id="SHOP-0001",
        jwt_secret="test-secret-32-bytes-minimum-value",
        allow_l2_simulation=True,
        platform_gate_max="L2",
    )


@pytest.fixture()
def m2_container(m2_settings: Settings) -> AppContainer:
    return build_container(m2_settings)


@pytest.fixture()
def m2_seeded(m2_container: AppContainer) -> AppContainer:
    seed_identity(m2_container)
    return m2_container


@pytest.fixture()
def m2_client(m2_seeded: AppContainer) -> TestClient:
    app = create_app(m2_seeded.settings, container=m2_seeded)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def m2_headers(m2_client: TestClient) -> dict[str, str]:
    return _login(m2_client, "owner", "owner123")


@pytest.fixture()
def m2_editor_headers(m2_client: TestClient) -> dict[str, str]:
    return _login(m2_client, "editor", "editor123")
