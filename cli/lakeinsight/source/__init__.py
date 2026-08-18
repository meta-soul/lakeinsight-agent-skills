"""Abstract skill source protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .. import logger

LOG = logger.LOG


class SkillSource(ABC):
    """Protocol that every skill provider must implement.

    Concrete implementation: ``GitHubSource`` (the default), selected via the
    ``--source`` option.  ``LocalSource`` is an internal directory reader.
    """

    name: str = "base"

    @abstractmethod
    def list_skills(self) -> dict[str, SkillSpec]:
        """Return all available skills as {name: SkillSpec}."""

    @abstractmethod
    def get_skill(self, name: str) -> SkillSpec | None:
        """Return a single skill spec, or None if not found."""

    @abstractmethod
    def list_versions(self, name: str) -> list[Version]:
        """Return available versions for a skill (sorted oldest→newest)."""

    def resolve_version(self, name: str, constraint: str) -> Version | None:
        """Return the best version satisfying ``constraint``.

        ``*`` → latest; ``>=1.0`` → first match; ``1.2.3`` → exact.
        """
        versions = self.list_versions(name)
        if not versions:
            return None
        from ..spec import VersionRange

        vr = VersionRange(constraint)
        for v in reversed(versions):
            if vr.satisfied_by(v):
                return v
        if constraint == "*":
            return versions[-1]
        return None

    @abstractmethod
    def download(self, name: str, version: Version, target: Path) -> Path:
        """Download / copy the skill to ``target`` directory; return target.

        ``target`` must be the final skill directory (e.g. ~/.lakeinsight/skills/foo).
        """

    def sync_manifest(self, manifest_path: Path) -> dict[str, SkillSpec]:
        """Refresh the local manifest.yaml from this source."""
        from ..manifest import write_skill_specs

        specs = self.list_skills()
        write_skill_specs(specs, manifest_path)
        LOG.info("已同步 %s → %d 个 skill", manifest_path, len(specs))
        return specs
