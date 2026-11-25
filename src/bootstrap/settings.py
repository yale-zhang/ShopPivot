"""运行时配置（环境变量前缀 SHOPPIVOT_）。"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.gate_level import GateLevel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHOPPIVOT_", env_file=".env", extra="ignore"
    )

    env: str = "dev"
    database_url: str = "sqlite:///./storage/shoppivot.db"
    storage_dir: Path = Path("./storage")
    modules_dir: Path = Path("./modules")

    jwt_secret: str = "dev-only-change-me-32-bytes-minimum"
    jwt_ttl_minutes: int = 480

    platform_source: str = "demo"
    platform: str = "demo"
    shop_id: str = "SHOP-0001"
    platform_gate_max: GateLevel = GateLevel.L2_MANUAL_APPROVAL
    allow_l2_simulation: bool = True
    credential_scopes: list[str] = Field(
        default_factory=lambda: ["pdd:report:read", "demo:report:read"]
    )

    daily_report_cron: str = "0 8 * * *"
    timezone: str = "Asia/Shanghai"
    redis_url: str = ""
    export_dir: Path = Path("./storage/exports")

    log_level: str = "INFO"

    @field_validator("platform_gate_max", mode="before")
    @classmethod
    def _gate(cls, value: object) -> GateLevel:
        return GateLevel.parse(value)

    @property
    def readonly_mode(self) -> bool:
        """平台上限为 L0 时全局只读（M0 恒为 True）。"""
        return self.platform_gate_max.rank < GateLevel.L2_MANUAL_APPROVAL.rank

    def ensure_dirs(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
