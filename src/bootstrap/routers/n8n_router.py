"""n8n 业务编排面 ACL（ADR-09 / D1）。

画布只持只读 / 建议 token，命令白名单，只能触发只读场景；
写入凭据与 /write 不在画布可达范围内。
"""
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from bootstrap.container import AppContainer, run_scene
from bootstrap.deps import get_container
from kernel.contexts.observability.domain.models import AuditEntry
from shared.errors.registry import DomainError

router = APIRouter(prefix="/api/v1/n8n", tags=["n8n"])

ALLOWED_COMMANDS = {"job.start"}
ALLOWED_SCENES = {"S01", "S04", "S05", "S07", "S09"}


class N8nCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=64)
    scene: str = Field(pattern=r"^S\d{2}$")
    day: date | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)
    requested_by: str = Field(default="n8n", max_length=64)


@router.post("/command")
def command(
    body: N8nCommandRequest,
    request: Request,
    container: AppContainer = Depends(get_container),
) -> dict:
    token = request.headers.get("x-api-token", "").strip()
    scope = container.api_tokens.resolve(token) if token else None
    if scope is None:
        container.n8n_commands.record(
            command=body.command, token_scope="", accepted=False, detail="invalid token"
        )
        raise DomainError("E002", "n8n 命令需要有效的机器 token")
    if scope not in {"READONLY", "SUGGEST"}:
        container.n8n_commands.record(
            command=body.command, token_scope=scope, accepted=False, detail="scope denied"
        )
        raise DomainError("E003", f"画布 token scope 不允许触发运行: {scope}")
    if body.command not in ALLOWED_COMMANDS:
        container.n8n_commands.record(
            command=body.command, token_scope=scope, accepted=False, detail="command not allowed"
        )
        raise DomainError("E003", f"命令不在白名单: {body.command}")
    if body.scene not in ALLOWED_SCENES:
        container.n8n_commands.record(
            command=body.command, token_scope=scope, accepted=False, detail="scene not allowed"
        )
        raise DomainError("E006", f"场景不在画布白名单: {body.scene}", status_override=400)

    result = run_scene(
        container,
        body.scene,
        day=body.day.isoformat() if body.day else None,
        requested_by=f"n8n:{body.requested_by}",
        trigger_type="EVENT",
    )
    container.n8n_commands.record(
        command=body.command,
        token_scope=scope,
        accepted=True,
        detail=f"scene={body.scene}",
        run_id=result.run.run_id.value,
    )
    container.audit.record(
        AuditEntry(
            actor=f"n8n:{body.requested_by}",
            action="n8n.command",
            object_type="run",
            object_id=result.run.run_id.value,
            after={"command": body.command, "scene": body.scene, "scope": scope},
        )
    )
    return {
        "run_id": result.run.run_id.value,
        "status": result.run.status.value,
        "scene": body.scene,
        "deduplicated": result.deduplicated,
    }


@router.get("/commands")
def recent_commands(
    request: Request,
    container: AppContainer = Depends(get_container),
) -> dict:
    token = request.headers.get("x-api-token", "").strip()
    if not token or container.api_tokens.resolve(token) is None:
        raise DomainError("E002", "需要机器 token")
    return {"items": container.n8n_commands.recent(50)}
