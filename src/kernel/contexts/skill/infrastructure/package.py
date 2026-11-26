"""Skill 包安全解压与校验。

只接受 zip；拒绝绝对路径、`..`、符号链接、超量文件/解压体积。
"""
from __future__ import annotations

import hashlib
import shutil
import stat
import zipfile
from pathlib import Path

from kernel.contexts.skill.domain.models import SkillUnavailable

MAX_FILES = 500
MAX_TOTAL_BYTES = 50 * 1024 * 1024


class SkillPackageError(SkillUnavailable):
    pass


def package_checksum(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(zip_path: str | Path, destination: str | Path) -> int:
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    total = 0
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES:
                raise SkillPackageError(f"Skill 包文件数超限: {len(infos)}")
            for info in infos:
                name = info.filename
                parts = Path(name).parts
                if name.startswith("/") or ".." in parts or not parts:
                    raise SkillPackageError(f"非法包路径: {name}")
                mode = (info.external_attr >> 16) & 0xF000
                if mode == stat.S_IFLNK:
                    raise SkillPackageError(f"包内不允许符号链接: {name}")
                total += info.file_size
                if total > MAX_TOTAL_BYTES:
                    raise SkillPackageError("Skill 包解压体积超限")
                target = (dest / name).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise SkillPackageError(f"路径越界: {name}")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
    except zipfile.BadZipFile as exc:
        raise SkillPackageError(f"不是合法 zip: {exc}") from exc
    return count
