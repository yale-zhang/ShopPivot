"""Celery 定时任务：S01 日报与 L2 超时作废（控制面常驻进程）。"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from bootstrap.container import build_container, run_daily, run_scene
from bootstrap.settings import get_settings
from kernel.contexts.approval.application.escalation import EscalateApprovalsUseCase
from kernel.contexts.approval.application.use_cases import ExpireApprovalsUseCase

settings = get_settings()
app = Celery(
    "shoppivot",
    broker=settings.redis_url or "memory://",
    backend=settings.redis_url or None,
)
app.conf.timezone = settings.timezone
app.conf.beat_schedule = {
    "daily-report-s01": {
        "task": "shoppivot.run_daily",
        "schedule": crontab(minute=0, hour=8),
    },
    "stock-recon-s07": {
        "task": "shoppivot.run_scene",
        "schedule": crontab(minute=0, hour=9),
        "args": ("S07",),
    },
    "review-patrol-s05": {
        "task": "shoppivot.run_scene",
        "schedule": crontab(minute=0, hour=10),
        "args": ("S05",),
    },
    "ad-monitor-s04": {
        "task": "shoppivot.run_scene",
        "schedule": crontab(minute=0, hour=11),
        "args": ("S04",),
    },
    "settlement-recon-s09": {
        "task": "shoppivot.run_scene",
        "schedule": crontab(minute=0, hour=2, day_of_month=1),
        "args": ("S09",),
    },
    "escalate-approvals": {
        "task": "shoppivot.escalate_approvals",
        "schedule": crontab(minute="*/5"),
    },
}


@app.task(name="shoppivot.run_daily")
def run_daily_task(day: str | None = None) -> dict:
    container = build_container()
    result = run_daily(container, day=day, requested_by="scheduler", trigger_type="SCHEDULE")
    return {
        "run_id": result.run.run_id.value,
        "status": result.run.status.value,
        "err_code": result.run.err_code,
    }


@app.task(name="shoppivot.run_scene")
def run_scene_task(scene: str, day: str | None = None) -> dict:
    container = build_container()
    result = run_scene(
        container, scene, day=day, requested_by="scheduler", trigger_type="SCHEDULE"
    )
    return {
        "run_id": result.run.run_id.value,
        "scene": scene,
        "status": result.run.status.value,
        "err_code": result.run.err_code,
    }


@app.task(name="shoppivot.escalate_approvals")
def escalate_approvals_task() -> dict:
    container = build_container()
    result = EscalateApprovalsUseCase(
        container.approvals, container.notifier, clock=container.clock
    )()
    return result.to_dict()


@app.task(name="shoppivot.expire_approvals")
def expire_approvals_task() -> dict:
    container = build_container()
    expired = ExpireApprovalsUseCase(container.approvals, clock=container.clock)()
    return {"expired": expired}
