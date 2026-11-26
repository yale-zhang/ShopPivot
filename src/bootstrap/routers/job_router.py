"""Worker API（表 6-10）：/job/start、/job/query、/suggest、/write、/callback、/heartbeat、/capabilities。"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request

from bootstrap.container import AppContainer
from bootstrap.deps import SessionUser, assert_shop_scope, get_container, get_current_user
from kernel.contexts.execution.domain.worker import Worker, WorkerKind, WorkerStatus
from kernel.contexts.identity.domain.account import Permission, has_permission
from kernel.contexts.orchestration.application.start_run import StartRunCommand
from kernel.contexts.orchestration.domain.run import NodeExecution, NodeStatus
from kernel.contracts.worker_api import (
    CallbackRequest,
    CapabilitiesResponse,
    HeartbeatRequest,
    JobQueryResponse,
    JobStartRequest,
    JobStartResponse,
    JobStatus,
    TriggerType,
    NodeExecutionView,
    ProposalItem,
    SuggestRequest,
    SuggestResponse,
    WriteRequest,
    WriteResponse,
)
from shared.errors.registry import DomainError
from shared.run_id import RunId

router = APIRouter(prefix="/api/v1", tags=["worker-api"])


def _session_or_machine(request: Request, container: AppContainer) -> SessionUser | str:
    if request.headers.get("authorization"):
        return get_current_user(request, container)
    token = request.headers.get("x-api-token", "").strip()
    if token:
        scope = container.api_tokens.resolve(token)
        if scope:
            return scope
    raise DomainError("E002", "需要会话令牌或机器 token")


def _job_status(value: str) -> JobStatus:
    return JobStatus(value)


@router.post("/job/start", response_model=JobStartResponse)
def start_job(
    body: JobStartRequest,
    request: Request,
    container: AppContainer = Depends(get_container),
) -> JobStartResponse:
    caller = _session_or_machine(request, container)
    if isinstance(caller, SessionUser):
        if not has_permission(caller.role, Permission.TRIGGER_RUN):
            raise DomainError("E003", "当前角色不能触发运行")
        assert_shop_scope(caller, body.platform, body.shop_id)
        requested_by = caller.username
    else:
        if caller not in {"READONLY", "SUGGEST"}:
            raise DomainError("E002", f"机器 token scope 不允许触发运行: {caller}")
        requested_by = f"token:{caller}"

    command = StartRunCommand(
        app_id=body.app_id,
        scene=body.scene,
        platform=body.platform,
        shop_id=body.shop_id,
        window_start=body.window_start,
        window_end=body.window_end,
        trigger_type=body.trigger_type.value,
        requested_by=requested_by,
        idempotency_key=body.idempotency_key,
        config_ref=body.config_ref,
        params=body.params,
    )
    result = container.pipeline(command)
    return JobStartResponse(
        run_id=result.run.run_id.value,
        status=_job_status(result.run.status.value),
        accepted_at=datetime.now(UTC),
        deduplicated=result.deduplicated,
    )


@router.get("/job/query", response_model=JobQueryResponse)
def query_job(
    request: Request,
    run_id: str = Query(min_length=8),
    container: AppContainer = Depends(get_container),
) -> JobQueryResponse:
    _ = _session_or_machine(request, container)
    run = container.runs.get(RunId.parse(run_id))
    if run is None:
        raise DomainError("E008", f"运行不存在: {run_id}", status_override=404)
    reports = [r.report_id for r in container.reports.recent(50) if r.run_id == run.run_id]
    return JobQueryResponse(
        run_id=run.run_id.value,
        app_id=run.app_id,
        scene=run.scene,
        platform=run.platform,
        shop_id=run.shop_id,
        status=_job_status(run.status.value),
        trigger_type=TriggerType(run.trigger_type),
        started_at=run.started_at,
        ended_at=run.ended_at,
        config_snapshot_hash=run.config_snapshot.hash,
        gate_level_max=run.gate_level_max,
        nodes=[
            NodeExecutionView(
                node_id=node.node_id,
                status=node.status.value,
                cost_ms=node.cost_ms,
                err_code=node.err_code,
                err_layer=node.err_layer,
            )
            for node in run.nodes
        ],
        report_refs=reports,
    )


@router.post("/suggest", response_model=SuggestResponse)
def suggest(
    body: SuggestRequest,
    request: Request,
    container: AppContainer = Depends(get_container),
) -> SuggestResponse:
    caller = _session_or_machine(request, container)
    if isinstance(caller, SessionUser):
        assert_shop_scope(caller, container.settings.platform, container.settings.shop_id)
    run = container.runs.get(RunId.parse(body.run_id))
    if run is None:
        raise DomainError("E008", f"运行不存在: {body.run_id}", status_override=404)
    decision = container.gate.decide(f"{run.scene}.report")
    return SuggestResponse(
        run_id=run.run_id.value,
        gate_level=decision.gate_level,
        proposals=[ProposalItem(target="无", impact="该场景为只读，未生成写入建议")],
        impact_scope="L0 只读：不改变平台经营数据",
        evidence_refs=[item["payload_hash"] for item in container.ods.by_run(run.run_id)],
    )


@router.post("/write", response_model=WriteResponse)
def write(
    body: WriteRequest,
    container: AppContainer = Depends(get_container),
) -> WriteResponse:
    raise DomainError(
        "E007",
        "写入必须经闸门：请使用 /write-plans 审批链路；画布/业务端不可直调 /write",
        details={"task_id": body.task_id, "gate": "write_plan_only"},
    )


@router.post("/callback")
def callback(
    body: CallbackRequest,
    request: Request,
    container: AppContainer = Depends(get_container),
) -> dict:
    caller = _session_or_machine(request, container)
    if isinstance(caller, SessionUser):
        raise DomainError("E002", "结果回调只接受机器 token")
    run = container.runs.get(RunId.parse(body.run_id))
    if run is None:
        raise DomainError("E008", f"运行不存在: {body.run_id}", status_override=404)
    status = NodeStatus(body.status.value)
    run.record_node(
        NodeExecution(
            node_id=body.node_id,
            status=status,
            cost_ms=body.cost_ms,
            channel=body.channel,
            err_code=body.err_code,
            err_layer=body.err_layer,
            payload_digest=body.payload_digest,
        )
    )
    container.runs.save(run)
    return {"ok": True, "run_id": run.run_id.value, "node_id": body.node_id}


@router.post("/heartbeat")
def heartbeat(
    body: HeartbeatRequest,
    request: Request,
    container: AppContainer = Depends(get_container),
) -> dict:
    caller = _session_or_machine(request, container)
    if isinstance(caller, SessionUser):
        raise DomainError("E002", "心跳只接受机器 token")
    container.workers.upsert(
        Worker(
            worker_id=body.worker_id,
            kind=WorkerKind(body.kind),
            status=WorkerStatus(body.status),
            capabilities=body.capabilities,
            queue_depth=body.queue_depth,
        )
    )
    return {"ok": True, "kernel_api": "1.0"}


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(
    request: Request,
    worker_id: str = Query(default="worker-headless-1"),
    container: AppContainer = Depends(get_container),
) -> CapabilitiesResponse:
    _session_or_machine(request, container)
    caps: list[str] = []
    for contribution in container.registry.by_kind("WorkerCapability"):
        capability = str(contribution.config.get("capability", contribution.id))
        if capability not in caps:
            caps.append(capability)
    return CapabilitiesResponse(
        worker_id=worker_id,
        kind="HEADLESS",
        capabilities=caps,
        kernel_api="1.0",
    )


@router.post("/worker/register-demo")
def register_demo_worker(
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict:
    """本地/测试用：把无桌面 Worker 注册进机群，供 P11 展示（仅 OWNER）。"""
    if user.role.value != "OWNER":
        raise DomainError("E003", "该操作仅 OWNER 可执行")
    worker_id = "worker-headless-1"
    caps = [
        str(c.config.get("capability", c.id))
        for c in container.registry.by_kind("WorkerCapability")
    ]
    container.workers.upsert(
        Worker(worker_id=worker_id, kind=WorkerKind.HEADLESS, capabilities=caps)
    )
    return {"worker_id": worker_id, "capabilities": caps}
