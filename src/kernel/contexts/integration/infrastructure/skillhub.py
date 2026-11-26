"""1688 Skill Hub 注册表客户端（只做检索/详情/下载，不自动安装执行）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from kernel.contexts.integration.domain.sourcing import ProviderUnavailable


@dataclass(frozen=True)
class SkillInfo:
    id: str
    name: str
    description: str
    latest_version: str = ""
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "latest_version": self.latest_version,
            "tags": list(self.tags),
        }


class SkillHubClient:
    def __init__(
        self,
        base_url: str = "https://clawhub.1688.com",
        *,
        token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def search(self, query: str, limit: int = 20) -> list[SkillInfo]:
        payload = self._get(
            "/api/v1/skills", params={"search": query, "limit": max(1, min(limit, 50))}
        )
        return [self._to_info(item) for item in payload.get("data", {}).get("items", [])]

    def detail(self, skill_id: str) -> dict[str, Any]:
        payload = self._get(f"/api/v1/skills/{quote(skill_id, safe='')}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderUnavailable(f"Skill 详情为空: {skill_id}")
        return data

    def versions(self, skill_id: str) -> list[dict[str, Any]]:
        payload = self._get(f"/api/v1/skills/{quote(skill_id, safe='')}/versions")
        data = payload.get("data")
        return data if isinstance(data, list) else []

    def download(self, skill_id: str, version: str | None = None) -> bytes:
        params = {"version": version} if version else None
        try:
            response = httpx.get(
                f"{self.base_url}/api/v1/skills/{quote(skill_id, safe='')}/download",
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"下载 Skill 失败: {exc}") from exc
        if response.status_code != 200:
            raise ProviderUnavailable(f"下载 Skill 返回 {response.status_code}")
        return response.content

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = httpx.get(
                f"{self.base_url}{path}",
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Skill Hub 不可达: {exc}") from exc
        if response.status_code != 200:
            raise ProviderUnavailable(f"Skill Hub 返回 {response.status_code}")
        payload: dict[str, Any] = dict(response.json())
        if not payload.get("success"):
            raise ProviderUnavailable(
                f"Skill Hub 业务错误: {str(payload.get('error'))[:200]}"
            )
        return payload

    @staticmethod
    def _to_info(item: dict[str, Any]) -> SkillInfo:
        return SkillInfo(
            id=str(item.get("id") or item.get("name") or ""),
            name=str(item.get("name") or ""),
            description=str(item.get("description") or ""),
            latest_version=str(item.get("latestVersion") or item.get("latest_version") or ""),
            tags=tuple(str(tag) for tag in (item.get("tags") or [])),
        )
