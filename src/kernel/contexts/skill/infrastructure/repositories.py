"""SkillRun 持久化。"""
from __future__ import annotations

from sqlalchemy import select

from kernel.contexts.skill.domain.models import SkillBinding, SkillInstallation, SkillRun
from kernel.contexts.skill.domain.ports import (
    SkillBindingRepository,
    SkillInstallationRepository,
    SkillRunRepository,
)
from kernel.persistence.base import Database
from kernel.persistence.tables import SkillBindingRow, SkillInstallationRow, SkillRunRow


class SqlSkillRunRepository(SkillRunRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def record(self, run: SkillRun) -> None:
        with self.db.session() as session:
            session.add(
                SkillRunRow(
                    run_id=run.run_id,
                    skill_id=run.skill_id,
                    skill_version=run.skill_version,
                    capability=run.capability,
                    scene=run.scene,
                    platform=run.platform,
                    shop_id=run.shop_id,
                    status=run.status,
                    input_digest=run.input_digest,
                    output_digest=run.output_digest,
                    latency_ms=run.latency_ms,
                    error_code=run.error_code,
                    created_at=run.created_at,
                )
            )

    def recent(self, limit: int = 50) -> list[SkillRun]:
        with self.db.session() as session:
            rows = session.execute(
                select(SkillRunRow).order_by(SkillRunRow.id.desc()).limit(limit)
            ).scalars().all()
            return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: SkillRunRow) -> SkillRun:
        return SkillRun(
            run_id=row.run_id,
            skill_id=row.skill_id,
            skill_version=row.skill_version,
            capability=row.capability,
            scene=row.scene,
            platform=row.platform,
            shop_id=row.shop_id,
            status=row.status,
            input_digest=row.input_digest,
            output_digest=row.output_digest,
            latency_ms=row.latency_ms,
            error_code=row.error_code,
            created_at=row.created_at,
        )


class SqlSkillInstallationRepository(SkillInstallationRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def get(self, skill_id: str) -> SkillInstallation | None:
        with self.db.session() as session:
            row = session.get(SkillInstallationRow, skill_id)
            return self._to_domain(row) if row else None

    def upsert(self, installation: SkillInstallation) -> None:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        with self.db.session() as session:
            row = session.get(SkillInstallationRow, installation.skill_id)
            if row is None:
                row = SkillInstallationRow(
                    skill_id=installation.skill_id,
                    installed_at=installation.installed_at or now,
                )
                session.add(row)
            row.version = installation.version
            row.status = installation.status
            row.checksum = installation.checksum
            row.manifest_path = installation.manifest_path
            row.installed_by = installation.installed_by
            row.details = installation.details
            row.updated_at = now

    def all(self) -> list[SkillInstallation]:
        with self.db.session() as session:
            rows = session.execute(select(SkillInstallationRow)).scalars().all()
            return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: SkillInstallationRow) -> SkillInstallation:
        return SkillInstallation(
            skill_id=row.skill_id,
            version=row.version,
            status=row.status,
            checksum=row.checksum,
            manifest_path=row.manifest_path,
            installed_by=row.installed_by,
            details=dict(row.details or {}),
            installed_at=row.installed_at,
            updated_at=row.updated_at,
        )


class SqlSkillBindingRepository(SkillBindingRepository):
    def __init__(self, database: Database) -> None:
        self.db = database

    def get(self, skill_id: str, platform: str, shop_id: str) -> SkillBinding | None:
        with self.db.session() as session:
            row = session.execute(
                select(SkillBindingRow).where(
                    SkillBindingRow.skill_id == skill_id,
                    SkillBindingRow.platform == platform,
                    SkillBindingRow.shop_id == shop_id,
                )
            ).scalar_one_or_none()
            return self._to_domain(row) if row else None

    def list_for_skill(self, skill_id: str) -> list[SkillBinding]:
        with self.db.session() as session:
            rows = session.execute(
                select(SkillBindingRow)
                .where(SkillBindingRow.skill_id == skill_id)
                .order_by(SkillBindingRow.priority.desc())
            ).scalars().all()
            return [self._to_domain(row) for row in rows]

    def upsert(self, binding: SkillBinding) -> None:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        with self.db.session() as session:
            row = session.execute(
                select(SkillBindingRow).where(
                    SkillBindingRow.skill_id == binding.skill_id,
                    SkillBindingRow.platform == binding.platform,
                    SkillBindingRow.shop_id == binding.shop_id,
                )
            ).scalar_one_or_none()
            if row is None:
                row = SkillBindingRow(
                    skill_id=binding.skill_id,
                    platform=binding.platform,
                    shop_id=binding.shop_id,
                    created_at=now,
                )
                session.add(row)
            row.enabled = binding.enabled
            row.priority = binding.priority
            row.credential_ref = binding.credential_ref
            row.config = binding.config
            row.updated_at = now

    def delete(self, skill_id: str, platform: str, shop_id: str) -> None:
        with self.db.session() as session:
            session.query(SkillBindingRow).filter(
                SkillBindingRow.skill_id == skill_id,
                SkillBindingRow.platform == platform,
                SkillBindingRow.shop_id == shop_id,
            ).delete()

    @staticmethod
    def _to_domain(row: SkillBindingRow) -> SkillBinding:
        return SkillBinding(
            skill_id=row.skill_id,
            platform=row.platform,
            shop_id=row.shop_id,
            enabled=row.enabled,
            priority=row.priority,
            credential_ref=row.credential_ref,
            config=dict(row.config or {}),
        )
