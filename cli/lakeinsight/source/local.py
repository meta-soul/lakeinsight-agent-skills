"""LocalSource — internal directory reader for skills.

Not a user-selectable source anymore (see ``resolve_source``).  It is used
internally by:

- ``GitHubSource`` to read the cloned repository directory,
- the ``dev sync`` command to generate ``manifest.yaml`` from a local repo,
- tests to build temporary skill fixtures.

Directory layouts (multi-version optional)::

    skills/
    └── bi-task/
        ├── 1.0.0/SKILL.md
        ├── 1.1.0/SKILL.md
        └── latest  →   1.1.0   (symlink or just the top-level SKILL.md)

Single-version legacy layout::

    skills/
    └── bi-task/
        └── SKILL.md
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from .. import logger

from ..config import REPO_ROOT
from ..errors import DownloadError, SkillNotFoundError
from ..spec import SkillSpec, Version

from . import SkillSource

LOG = logger.LOG

SKILL_FILE = "SKILL.md"
_VERSION_DIR_RE = re.compile(r"^\d+\.\d+\.\d+$")


class LocalSource(SkillSource):
    """Internal directory reader (not a user-selectable source)."""

    name = "local"

    def __init__(self, root: Path | None = None, version_separate: bool = False) -> None:
        self._root = root or (REPO_ROOT / "skills")
        LOG.debug("LocalSource root=%s", self._root)

    def list_skills(self) -> dict[str, SkillSpec]:
        if not self._root.exists():
            return {}
        specs: dict[str, SkillSpec] = {}
        for child in sorted(p for p in self._root.iterdir() if p.is_dir()):
            if child.name.startswith((".", "_")):
                continue
            spec = self._read_skill_spec(child)
            if spec is not None:
                specs[spec.name] = spec
        return specs

    def get_skill(self, name: str) -> SkillSpec | None:
        source_dir = self._root / name
        if not source_dir.is_dir():
            return None
        return self._read_skill_spec(source_dir)

    def list_versions(self, name: str) -> list[Version]:
        source_dir = self._root / name
        if not source_dir.is_dir():
            return []
        versions: list[Version] = []
        for child in source_dir.iterdir():
            if child.is_dir() and _VERSION_DIR_RE.match(child.name):
                v = Version.parse(child.name)
                if str(v) != "0.0.0":
                    versions.append(v)
        if not versions:
            spec = self._read_skill_spec(source_dir)
            if spec:
                versions = [spec.version]
        versions.sort()
        return versions

    @staticmethod
    def _parse_frontmatter(text: str) -> dict[str, Any]:
        if not text.startswith("---"):
            return {}
        end = text.find("\n---", 3)
        if end == -1:
            return {}
        block = text[3:end].strip()
        try:
            data = yaml.safe_load(block)
        except yaml.YAMLError:
            return {}
        return data if isinstance(data, dict) else {}

    def _read_skill_spec(self, dir: Path) -> SkillSpec | None:
        skill_file = dir / SKILL_FILE
        if not skill_file.exists():
            return None
        fm = self._parse_frontmatter(skill_file.read_text(encoding="utf-8"))
        name = str(fm.get("name") or dir.name)
        spec = SkillSpec.from_dict(name, fm)
        if spec.version == Version(0, 0, 0):
            spec.version = self._latest_version_dir(dir) or spec.version
        return spec

    def _latest_version_dir(self, parent: Path) -> Version | None:
        best: Version | None = None
        for child in parent.iterdir():
            if child.is_dir() and _VERSION_DIR_RE.match(child.name):
                v = Version.parse(child.name)
                if best is None or v > best:
                    best = v
        return best

    def _version_dir(self, name: str, version: Version) -> Path:
        """Return the source path for a specific version.

        Tries ``skills/<name>/<version>/`` first,
        otherwise falls back to ``skills/<name>/``.
        """
        versioned = self._root / name / str(version)
        if versioned.is_dir():
            return versioned
        flat = self._root / name
        if flat.is_dir():
            return flat
        raise SkillNotFoundError(name)

    def download(self, name: str, version: Version, target: Path) -> Path:
        source_dir = self._version_dir(name, version)
        if not source_dir.is_dir():
            raise SkillNotFoundError(name)
        spec = self._read_skill_spec(source_dir)
        if spec is None:
            raise SkillNotFoundError(name)
        if spec.version != version:
            raise DownloadError(
                name, f"local 源仅有版本 {spec.version}，请求的是 {version}"
            )
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source_dir, target)
        LOG.debug("copied %s → %s", source_dir, target)
        return target
