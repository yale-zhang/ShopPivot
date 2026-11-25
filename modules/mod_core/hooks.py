"""mod_core 幂等启动钩子。"""
from __future__ import annotations

import logging

log = logging.getLogger("shoppivot.modules.core")


def on_startup() -> None:
    log.info("module startup", extra={"module": "mod_core", "version": "1.0.0"})
