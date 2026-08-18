"""Install state tracking (~/.lakeinsight/state.yaml).

Contains **only** install status — never skill definitions.

A skill can be installed to multiple agents / scopes.  Each such install is an
:class:`Installation`, addressed by a stable ``id`` so a single agent/scope can
be removed without affecting the others.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .config import STATE_PATH
from .errors import InvalidStateError
from .spec import Version


def make_installation_id(agent: str, scope: str, root: str, skill: str) -> str:
    """Stable id = sha256(agent + scope + root + skill)[:8]."""
    raw = f"{agent}|{scope}|{root}|{skill}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:8]


def _slug(root: str) -> str:
    if not root:
        return ""
    return Path(root).name


@dataclass
class Installation:
    """A single skill install into one agent/scope."""

    id: str
    agent: str
    scope: str          # global | project | custom
    path: str
    root: str = ""      # project root (project scope only)
    slug: str = ""      # display only
    resolver: str = ""  # detected | default (detect adapters)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "agent": self.agent,
            "scope": self.scope,
            "path": self.path,
        }
        if self.root:
            d["root"] = self.root
        if self.slug:
            d["slug"] = self.slug
        if self.resolver:
            d["resolver"] = self.resolver
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Installation:
        if not isinstance(data, dict):
            return cls(id="", agent="", scope="", path="")
        return cls(
            id=str(data.get("id", "")),
            agent=str(data.get("agent", "")),
            scope=str(data.get("scope", "")),
            path=str(data.get("path", "")),
            root=str(data.get("root", "")),
            slug=str(data.get("slug", "")),
            resolver=str(data.get("resolver", "")),
        )


@dataclass
class InstalledSkill:
    """Record of an installed skill (one or more installations)."""

    name: str
    version: Version
    installed_at: str = ""
    dependencies: list[str] = field(default_factory=list)
    installations: list[Installation] = field(default_factory=list)

    @property
    def install_path(self) -> str:
        """Back-compat: first installation path (or '')."""
        return self.installations[0].path if self.installations else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": str(self.version),
            "installed_at": self.installed_at,
            "dependencies": self.dependencies,
            "installations": [i.to_dict() for i in self.installations],
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> InstalledSkill:
        version = data.get("version")
        if isinstance(version, str):
            version = Version.parse(version)
        else:
            version = Version(0, 0, 0)

        installations: list[Installation] = []
        raw_installs = data.get("installations")
        if isinstance(raw_installs, list):
            for entry in raw_installs:
                installations.append(Installation.from_dict(entry))
        elif data.get("install_path"):
            # Migrate legacy single-path records into a custom installation.
            installations.append(
                Installation(
                    id=make_installation_id("custom", "global", "", name),
                    agent="custom",
                    scope="custom",
                    path=str(data.get("install_path")),
                )
            )

        return cls(
            name=name,
            version=version,
            installed_at=str(data.get("installed_at", "")),
            dependencies=list(data.get("dependencies", []) or []),
            installations=installations,
        )


def _default_state() -> dict[str, Any]:
    return {"installed": {}}


def load_state(path: Path | None = None) -> dict[str, Any]:
    p = path or STATE_PATH
    if not p.exists():
        return _default_state()
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise InvalidStateError("不是 YAML 对象")
    data.setdefault("installed", {})
    return data


def save_state(data: dict[str, Any], path: Path | None = None) -> None:
    p = path or STATE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)


def get_installed_skills(path: Path | None = None) -> dict[str, InstalledSkill]:
    data = load_state(path)
    result: dict[str, InstalledSkill] = {}
    for name, entry in (data.get("installed", {}) or {}).items():
        if isinstance(entry, dict):
            result[name] = InstalledSkill.from_dict(name, entry)
    return result


def set_installed_skill(installed: InstalledSkill, path: Path | None = None) -> None:
    data = load_state(path)
    data.setdefault("installed", {})[installed.name] = installed.to_dict()
    save_state(data, path)


def remove_installed_skill(name: str, path: Path | None = None) -> None:
    data = load_state(path)
    data.setdefault("installed", {}).pop(name, None)
    save_state(data, path)


def remove_installation(name: str, installation_id: str, path: Path | None = None) -> None:
    """Remove a single installation from a skill; drop the skill if none remain."""
    installed = get_installed_skills(path)
    entry = installed.get(name)
    if entry is None:
        return
    entry.installations = [i for i in entry.installations if i.id != installation_id]
    if not entry.installations:
        remove_installed_skill(name, path)
    else:
        set_installed_skill(entry, path)


def is_installed(name: str, path: Path | None = None) -> bool:
    return name in get_installed_skills(path)


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
