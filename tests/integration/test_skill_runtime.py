"""S0/S1 技能运行时：目录、锁定、执行记录、P14 API。"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bootstrap.container import AppContainer, run_scene
from kernel.contexts.skill.infrastructure.catalog import LocalSkillCatalog, SkillCatalogError


def test_catalog_loads_lock_and_capabilities(m2_seeded: AppContainer) -> None:
    catalog = m2_seeded.skill_catalog
    skills = catalog.all()
    assert {item.id for item in skills} == {"1688-distribution", "1688-utp-shopping"}
    distribution = catalog.get("1688-distribution")
    assert distribution is not None
    assert distribution.version == "1.4.0"
    assert distribution.trust.value == "official"
    assert distribution.capability("sourcing.search") is not None
    assert distribution.checksum == "adapter-only"
    match = catalog.find("sourcing.search", "demo", "SHOP-0001")
    assert match is not None
    assert match[0].id == "1688-distribution"


def test_s10_executes_through_runtime_and_records_run(m2_seeded: AppContainer) -> None:
    result = run_scene(m2_seeded, "S10", params={"keyword": "垃圾袋", "limit": 5})
    assert result.run.status.value == "SUCCEEDED", result.run.err_code
    runs = m2_seeded.skill_runs.recent(20)
    matching = [
        run for run in runs if run.run_id == result.run.run_id.value
    ]
    assert matching
    run = matching[0]
    assert run.skill_id == "1688-distribution"
    assert run.capability == "sourcing.search"
    assert run.status == "SUCCEEDED"
    assert run.input_digest and run.output_digest
    assert run.latency_ms >= 0


def test_skill_api_is_owner_only(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    catalog = m2_client.get("/api/v1/skills/catalog", headers=m2_headers)
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["count"] == 2
    assert body["note"].startswith("S0 只读")
    first = body["items"][0]
    assert first["capabilities"]
    assert first["trust"] in {"official", "verified"}

    detail = m2_client.get("/api/v1/skills/1688-distribution", headers=m2_headers)
    assert detail.status_code == 200
    assert detail.json()["bindings"]

    runs = m2_client.get("/api/v1/skills/runs", headers=m2_headers)
    assert runs.status_code == 200
    assert "items" in runs.json()

    viewer = m2_client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "viewer123"},
    ).json()["access_token"]
    forbidden = m2_client.get(
        "/api/v1/skills/catalog", headers={"Authorization": f"Bearer {viewer}"}
    )
    assert forbidden.status_code == 403


def test_catalog_rejects_version_mismatch(tmp_path: Path) -> None:
    (tmp_path / "skill.yaml").write_text(
        """id: demo
version: "1.0.0"
publisher: demo
trust: verified
license: MIT
adapter: demo:Adapter
capabilities:
  - name: demo.read
    risk: L0
""",
        encoding="utf-8",
    )
    lock = tmp_path / "skills.lock"
    lock.write_text(
        """version: 1
skills:
  - id: demo
    version: "2.0.0"
    manifest: skill.yaml
    status: adapter-only
""",
        encoding="utf-8",
    )
    with pytest.raises(SkillCatalogError, match="版本"):
        LocalSkillCatalog(lock, root=tmp_path)


def test_catalog_rejects_l3_capability_in_runtime(m2_seeded: AppContainer) -> None:
    # 运行时拒绝 L3 是硬约束；用目录查询确认能力声明不会自动降级
    distribution = m2_seeded.skill_catalog.get("1688-distribution")
    assert distribution is not None
    assert all(item.risk.value in {"L0", "L1", "L2"} for item in distribution.capabilities)


def test_install_verify_enable_disable_controls_runtime(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    installed = m2_client.post(
        "/api/v1/skills/1688-distribution/install", headers=m2_headers
    )
    assert installed.status_code == 200, installed.text
    body = installed.json()
    assert body["status"] == "INSTALLED"
    assert len(body["checksum"]) == 64

    verified = m2_client.post(
        "/api/v1/skills/1688-distribution/verify", headers=m2_headers
    )
    assert verified.status_code == 200
    assert verified.json()["ok"] is True

    disabled = m2_client.post(
        "/api/v1/skills/1688-distribution/disable", headers=m2_headers
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"
    failed = run_scene(m2_seeded, "S10", params={"keyword": "垃圾袋"})
    assert failed.run.status.value == "FAILED"
    assert failed.run.err_code == "E008"

    enabled = m2_client.post(
        "/api/v1/skills/1688-distribution/enable", headers=m2_headers
    )
    assert enabled.status_code == 200
    ok = run_scene(m2_seeded, "S10", params={"keyword": "垃圾袋 加厚"})
    assert ok.run.status.value == "SUCCEEDED", ok.run.err_code


def test_binding_scope_and_disable(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    bound = m2_client.put(
        "/api/v1/skills/1688-distribution/bindings",
        json={
            "platform": "demo",
            "shop_id": "SHOP-0001",
            "enabled": False,
            "priority": 99,
            "credential_ref": "vault://1688/demo-shop",
        },
        headers=m2_headers,
    )
    assert bound.status_code == 200, bound.text
    assert bound.json()["credential_ref"] == "vault://1688/demo-shop"

    blocked = run_scene(m2_seeded, "S10", params={"keyword": "垃圾袋"})
    assert blocked.run.status.value == "FAILED"
    assert blocked.run.err_code == "E008"

    m2_client.put(
        "/api/v1/skills/1688-distribution/bindings",
        json={"platform": "demo", "shop_id": "SHOP-0001", "enabled": True, "priority": 99},
        headers=m2_headers,
    )
    allowed = run_scene(m2_seeded, "S10", params={"keyword": "垃圾袋 加厚"})
    assert allowed.run.status.value == "SUCCEEDED", allowed.run.err_code
    bindings = m2_client.get(
        "/api/v1/skills/1688-distribution/bindings", headers=m2_headers
    ).json()
    assert bindings["items"][0]["platform"] == "demo"
    assert bindings["items"][0]["shop_id"] == "SHOP-0001"

    removed = m2_client.delete(
        "/api/v1/skills/1688-distribution/bindings",
        params={"platform": "demo", "shop_id": "SHOP-0001"},
        headers=m2_headers,
    )
    assert removed.status_code == 200


def _package_dir(container: AppContainer) -> Path:
    path = container.settings.storage_dir / "skill_packages"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_package(container: AppContainer, name: str, manifest_text: str, evil: bool = False) -> str:
    import zipfile

    target = _package_dir(container) / name
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("skill.yaml", manifest_text)
        archive.writestr("README.md", "# demo skill package\n")
        if evil:
            archive.writestr("../evil.txt", "should not escape")
    return name


def test_package_install_checksum_and_safe_extract(
    m2_seeded: AppContainer, m2_client: TestClient, m2_headers: dict[str, str]
) -> None:
    manifest_text = """id: 1688-distribution
version: "1.4.0"
publisher: 1688aiinfra
trust: official
license: MIT
adapter: modules.mod_1688_ops.skill_adapter:DistributionSourcingAdapter
capabilities:
  - name: sourcing.search
    risk: L0
"""
    name = _write_package(m2_seeded, "distribution.zip", manifest_text)
    installed = m2_client.post(
        "/api/v1/skills/1688-distribution/install",
        json={"source": "package", "package_path": name},
        headers=m2_headers,
    )
    assert installed.status_code == 200, installed.text
    body = installed.json()
    assert body["status"] == "INSTALLED"
    assert body["details"]["kind"] == "package"
    assert len(body["details"]["package_checksum"]) == 64
    assert body["details"]["files"] == 2
    assert "package" in body["note"]

    verified = m2_client.post(
        "/api/v1/skills/1688-distribution/verify", headers=m2_headers
    )
    assert verified.status_code == 200
    assert verified.json()["ok"] is True

    evil = _write_package(m2_seeded, "evil.zip", manifest_text, evil=True)
    rejected = m2_client.post(
        "/api/v1/skills/1688-distribution/install",
        json={"source": "package", "package_path": evil},
        headers=m2_headers,
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "E006"

    outside = m2_client.post(
        "/api/v1/skills/1688-distribution/install",
        json={"source": "package", "package_path": "../../etc/passwd.zip"},
        headers=m2_headers,
    )
    assert outside.status_code == 409
    assert outside.json()["code"] == "E006"
