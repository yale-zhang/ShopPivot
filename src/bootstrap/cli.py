"""命令行入口：seed / run-daily / 演示审批 / 模块状态。"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta

from bootstrap.container import AppContainer, build_container, run_daily, run_scene
from bootstrap.seed import seed_all
from kernel.contexts.approval.application.escalation import EscalateApprovalsUseCase
from kernel.contexts.approval.application.use_cases import ExpireApprovalsUseCase
from kernel.contexts.approval.application.write_flow import CreateWritePlanCommand
from kernel.contexts.approval.domain.approval_task import ApprovalTask
from kernel.contexts.observability.domain.models import AuditEntry
from shared.gate_level import GateLevel
from shared.run_id import RunId


def _container() -> AppContainer:
    return build_container()


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def cmd_seed(container: AppContainer, _args: argparse.Namespace) -> int:
    _print(seed_all(container))
    return 0


def cmd_run_daily(container: AppContainer, args: argparse.Namespace) -> int:
    result = run_daily(container, day=args.day, requested_by=args.user)
    run = result.run
    reports = [report for report in container.reports.recent(10) if report.run_id == run.run_id]
    payload = {
        "run_id": run.run_id.value,
        "status": run.status.value,
        "err_code": run.err_code,
        "err_layer": run.err_layer,
        "nodes": [
            {
                "node_id": node.node_id,
                "status": node.status.value,
                "cost_ms": node.cost_ms,
                "channel": node.channel.value if node.channel else None,
                "err_code": node.err_code,
            }
            for node in run.nodes
        ],
        "reports": [
            {
                "report_id": report.report_id,
                "artifact_ref": report.artifact_ref,
                "metric_version": report.metric_version,
                "watermark": report.watermark,
            }
            for report in reports
        ],
        "deduplicated": result.deduplicated,
    }
    _print(payload)
    return 0 if run.status.value == "SUCCEEDED" else 1


def cmd_run_scene(container: AppContainer, args: argparse.Namespace) -> int:
    result = run_scene(
        container, args.scene, day=args.day, requested_by=args.user
    )
    run = result.run
    _print(
        {
            "run_id": run.run_id.value,
            "scene": run.scene,
            "status": run.status.value,
            "err_code": run.err_code,
            "err_layer": run.err_layer,
            "nodes": [
                {
                    "node_id": node.node_id,
                    "status": node.status.value,
                    "cost_ms": node.cost_ms,
                    "channel": node.channel.value if node.channel else None,
                    "err_code": node.err_code,
                }
                for node in run.nodes
            ],
            "deduplicated": result.deduplicated,
            "details": result.scene_result.details if result.scene_result else {},
        }
    )
    return 0 if run.status.value == "SUCCEEDED" else 1


def cmd_create_demo_approval(container: AppContainer, args: argparse.Namespace) -> int:
    if not container.settings.allow_l2_simulation:
        print("allow_l2_simulation=false，拒绝创建演示 L2 待办", file=sys.stderr)
        return 2
    platform = container.settings.platform_source or container.settings.platform
    run = next(
        (item for item in container.runs.recent(20) if item.platform == platform),
        None,
    )
    if run is None:
        run_daily(container)
        run = next(
            (item for item in container.runs.recent(20) if item.platform == platform), None
        )
    if run is None:
        print("没有可用运行，无法创建演示待办", file=sys.stderr)
        return 1
    now = datetime.now(UTC)
    sla = now + timedelta(seconds=args.sla_seconds)
    task = ApprovalTask.request(
        run_id=run.run_id,
        gate_level=GateLevel.L2_MANUAL_APPROVAL,
        action_code="S02.price_update",
        write_plan={
            "created_at": now.isoformat(),
            "metric_version": "v1.0",
            "snapshot_time": now.isoformat(),
            "schema_version": "1.0",
            "rows": [
                {
                    "target": "SKU-A",
                    "field": "活动价",
                    "before": "¥89.00",
                    "after": "¥79.00",
                    "impact": "预计影响 3 个 SKU",
                },
                {
                    "target": "SKU-B",
                    "field": "活动价",
                    "before": "¥129.00",
                    "after": "¥119.00",
                    "impact": "跨 2 店铺",
                },
            ],
            "evidence": [
                {"kind": "metric_card", "ref": "metric.cvr@1.0", "label": "口径卡引用"},
                {"kind": "file_hash", "ref": "sha256:8f13…", "label": "导出文件哈希"},
                {"kind": "screenshot", "ref": "shot://before/SKU-A", "label": "变更前截图"},
                {"kind": "probe", "ref": "probe://gmv", "label": "探针实测值"},
            ],
            "rollback_plan": "改回上一稳定价（记录在 change_order），执行后逐条回查",
        },
        sla_expires_at=sla,
        idempotency_key=f"demo-approval:{run.run_id.value}:{args.sla_seconds}:{int(now.timestamp())}",
        scene="S02",
        platform=run.platform,
        shop_id=run.shop_id,
        impact_scope="金额区间 ¥2,400–3,100 · 跨 2 店铺 · impact_scope 多跳路径",
        requested_by=args.user,
    )
    container.approvals.add(task)
    container.audit.record(
        AuditEntry(
            actor=args.user,
            action="approval.demo_create",
            object_type="approval_task",
            object_id=task.task_id,
            reason="F-04 验收：构造 L2 超时待办（不签发 token、不执行写入）",
        )
    )
    if args.immediate_expire:
        expired = ExpireApprovalsUseCase(container.approvals, clock=container.clock)()
        task = container.approvals.get(task.task_id) or task
        _print(
            {
                "task_id": task.task_id,
                "status": task.status.value,
                "expired_now": expired,
                "note": "超时自动作废，未执行任何写入",
            }
        )
        return 0
    _print(
        {
            "task_id": task.task_id,
            "status": task.status.value,
            "sla_expires_at": task.sla_expires_at.isoformat(),
            "note": "等待超时或手动 expire-approvals；M0 不签发 WriteToken",
        }
    )
    return 0


def cmd_create_price_plan(container: AppContainer, args: argparse.Namespace) -> int:
    platform = container.settings.platform_source or container.settings.platform
    plan, task = container.write_flow.create_plan(
        CreateWritePlanCommand(
            action_code="S02.price_update",
            platform=platform,
            shop_id=container.settings.shop_id,
            rows=[{"sku": args.sku, "after": args.after}],
            requested_by=args.user,
            idempotency_key=args.idempotency_key
            or f"cli-price:{args.sku}:{args.after}:{args.user}",
        )
    )
    _print(
        {
            "plan_id": plan.plan_id,
            "status": plan.status.value,
            "task_id": task.task_id,
            "sla_expires_at": task.sla_expires_at.isoformat(),
            "rows": plan.rows,
            "impact_scope": plan.impact_scope,
            "approve": f"python -m bootstrap.cli approve-plan --plan-id {plan.plan_id}",
        }
    )
    return 0


def cmd_create_campaign_plan(container: AppContainer, args: argparse.Namespace) -> int:
    platform = container.settings.platform_source or container.settings.platform
    plan, task = container.write_flow.create_plan(
        CreateWritePlanCommand(
            action_code="S03.campaign_apply",
            platform=platform,
            shop_id=container.settings.shop_id,
            rows=[
                {
                    "campaign_id": args.campaign,
                    "sku": args.sku,
                    "activity_price": args.price,
                }
            ],
            requested_by=args.user,
            idempotency_key=args.idempotency_key
            or f"cli-campaign:{args.campaign}:{args.sku}:{args.price}",
        )
    )
    _print(
        {
            "plan_id": plan.plan_id,
            "status": plan.status.value,
            "task_id": task.task_id,
            "rows": plan.rows,
            "impact_scope": plan.impact_scope,
        }
    )
    return 0


def cmd_approve_plan(container: AppContainer, args: argparse.Namespace) -> int:
    plan, execution = container.write_flow.approve(
        args.plan_id, operator=args.user, reason=args.reason
    )
    _print(
        {
            "plan_id": plan.plan_id,
            "status": plan.status.value,
            "execution": {
                "execution_id": execution.execution_id if execution else None,
                "status": execution.status if execution else None,
                "verify_result": execution.verify_result if execution else None,
                "err_code": execution.err_code if execution else None,
            },
            "note": "写入经人工批准 + 一次性 token 执行；回查不一致会进入补偿",
        }
    )
    return 0 if plan.status.value in {"VERIFIED", "COMPENSATED"} else 1


def cmd_reject_plan(container: AppContainer, args: argparse.Namespace) -> int:
    plan = container.write_flow.reject(
        args.plan_id, operator=args.user, reason=args.reason
    )
    _print({"plan_id": plan.plan_id, "status": plan.status.value})
    return 0


def cmd_expire_approvals(container: AppContainer, _args: argparse.Namespace) -> int:
    expired = ExpireApprovalsUseCase(container.approvals, clock=container.clock)()
    _print({"expired": expired})
    return 0


def cmd_escalate_approvals(container: AppContainer, _args: argparse.Namespace) -> int:
    result = EscalateApprovalsUseCase(
        container.approvals, container.notifier, clock=container.clock
    )()
    _print(result.to_dict())
    return 0


def cmd_modules(container: AppContainer, _args: argparse.Namespace) -> int:
    report = container.startup_report
    _print(report.to_dict() if report else {"error": "modules not loaded"})
    return 0


def cmd_show_run(container: AppContainer, args: argparse.Namespace) -> int:
    run = container.runs.get(RunId.parse(args.run_id))
    if run is None:
        print("运行不存在", file=sys.stderr)
        return 1
    _print(
        {
            "run_id": run.run_id.value,
            "status": run.status.value,
            "err_code": run.err_code,
            "nodes": [
                {"node_id": n.node_id, "status": n.status.value, "cost_ms": n.cost_ms}
                for n in run.nodes
            ],
        }
    )
    return 0


def cmd_approve_note(_container: AppContainer, _args: argparse.Namespace) -> int:
    print(
        "M0 为只读模式：批准入口在 P06 置灰，/write 返回 403；"
        "WriteToken 与真实写入在 M2 启用。",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shoppivot", description="店枢 ShopPivot M0 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="初始化账号/店铺授权/机器 token").set_defaults(func=cmd_seed)

    run_parser = sub.add_parser("run-daily", help="执行一次 S01 经营日报")
    run_parser.add_argument("--day", default=None, help="统计日 YYYY-MM-DD，默认今天")
    run_parser.add_argument("--user", default="system")
    run_parser.set_defaults(func=cmd_run_daily)

    scene_parser = sub.add_parser("run-scene", help="执行指定场景（S01/S05/S07）")
    scene_parser.add_argument("--scene", required=True, choices=["S01", "S04", "S05", "S07"])
    scene_parser.add_argument("--day", default=None, help="统计日 YYYY-MM-DD，默认今天")
    scene_parser.add_argument("--user", default="system")
    scene_parser.set_defaults(func=cmd_run_scene)

    approval_parser = sub.add_parser("create-demo-approval", help="构造 F-04 演示 L2 待办")
    approval_parser.add_argument("--sla-seconds", type=int, default=120)
    approval_parser.add_argument("--immediate-expire", action="store_true")
    approval_parser.add_argument("--user", default="owner")
    approval_parser.set_defaults(func=cmd_create_demo_approval)

    price_parser = sub.add_parser("create-price-plan", help="创建 S02 价格变更计划（L2）")
    price_parser.add_argument("--sku", required=True)
    price_parser.add_argument("--after", required=True, help="目标价，如 79.00")
    price_parser.add_argument("--idempotency-key", default=None)
    price_parser.add_argument("--user", default="owner")
    price_parser.set_defaults(func=cmd_create_price_plan)

    campaign_parser = sub.add_parser("create-campaign-plan", help="创建 S03 活动提报计划（L2）")
    campaign_parser.add_argument("--campaign", required=True)
    campaign_parser.add_argument("--sku", required=True)
    campaign_parser.add_argument("--price", required=True, help="活动价，如 69.00")
    campaign_parser.add_argument("--idempotency-key", default=None)
    campaign_parser.add_argument("--user", default="owner")
    campaign_parser.set_defaults(func=cmd_create_campaign_plan)

    approve_parser = sub.add_parser("approve-plan", help="批准并执行 L2 计划")
    approve_parser.add_argument("--plan-id", required=True)
    approve_parser.add_argument("--reason", default="CLI 批准")
    approve_parser.add_argument("--user", default="owner")
    approve_parser.set_defaults(func=cmd_approve_plan)

    reject_parser = sub.add_parser("reject-plan", help="驳回 L2 计划")
    reject_parser.add_argument("--plan-id", required=True)
    reject_parser.add_argument("--reason", required=True)
    reject_parser.add_argument("--user", default="owner")
    reject_parser.set_defaults(func=cmd_reject_plan)

    sub.add_parser("expire-approvals", help="把超时 L2 待办置为 EXPIRED").set_defaults(
        func=cmd_expire_approvals
    )
    sub.add_parser("escalate-approvals", help="SLA 提醒/升级/超时作废").set_defaults(
        func=cmd_escalate_approvals
    )
    sub.add_parser("modules", help="打印模块装配报告").set_defaults(func=cmd_modules)

    run_show = sub.add_parser("show-run", help="查看运行状态")
    run_show.add_argument("run_id")
    run_show.set_defaults(func=cmd_show_run)

    sub.add_parser("approve-note", help="说明 M0 为什么不能批准写入").set_defaults(
        func=cmd_approve_note
    )

    args = parser.parse_args(argv)
    container = _container()
    return int(args.func(container, args))


if __name__ == "__main__":
    raise SystemExit(main())
