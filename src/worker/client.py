"""Worker API 客户端：心跳、能力登记、结果回调。"""
from __future__ import annotations

from typing import Any

import httpx


class WorkerClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Token": self.token}

    def capabilities(self, worker_id: str) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/api/v1/capabilities",
            params={"worker_id": worker_id},
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def heartbeat(
        self,
        *,
        worker_id: str,
        kind: str = "HEADLESS",
        status: str = "ONLINE",
        capabilities: list[str] | None = None,
        queue_depth: int = 0,
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/api/v1/heartbeat",
            json={
                "worker_id": worker_id,
                "kind": kind,
                "status": status,
                "capabilities": capabilities or [],
                "queue_depth": queue_depth,
            },
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def callback(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/api/v1/callback",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def query(self, run_id: str) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/api/v1/job/query",
            params={"run_id": run_id},
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
