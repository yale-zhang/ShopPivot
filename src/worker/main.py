"""M0 Worker 进程入口：登记能力并维持心跳。

说明：M0 的只读执行在控制面进程内完成（无桌面、无独立队列），
Worker 进程只承担能力登记与心跳；M2 拆分独立执行进程时，Worker API 契约不变。
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from worker.client import WorkerClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shoppivot-worker")
    parser.add_argument("--api", default=os.environ.get("SHOPPIVOT_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument(
        "--token",
        default=os.environ.get(
            "SHOPPIVOT_WORKER_TOKEN",
            str(Path("storage/worker.token")),
        ),
    )
    parser.add_argument("--worker-id", default="worker-headless-1")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)

    token = args.token
    if Path(token).is_file():
        token = Path(token).read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit("缺少 worker token：先运行 python -m bootstrap.cli seed")

    client = WorkerClient(args.api, token)
    capabilities = client.capabilities(args.worker_id)["capabilities"]
    print(f"worker {args.worker_id} capabilities={capabilities}")
    while True:
        try:
            client.heartbeat(worker_id=args.worker_id, capabilities=capabilities)
            print("heartbeat ok")
        except Exception as exc:  # noqa: BLE001 - 心跳失败不应让进程退出
            print(f"heartbeat failed: {exc}")
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
