"""SkillSpec — canonical skill descriptor including version / dependency semantics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_VERSION_RE = re.compile(
    r"^(?P<major>\d+)(?:\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?)?$"
)
_VERSION_CONSTRAINT_RE = re.compile(
    r"^(?P<op>[><=!~^]*)\s*(?P<ver>\d+(?:\.\d+)*(?:\.\d+)?)$"
)


@dataclass(order=True)
class Version:
    """A simple semver-like version (major.minor.patch)."""

    major: int = 0
    minor: int = 0
    patch: int = 0

    @classmethod
    def parse(cls, raw: str) -> Version:
        m = _VERSION_RE.match(raw.strip())
        if not m:
            return cls(0, 0, 0)
        return cls(
            int(m.group("major")),
            int(m.group("minor") or 0),
            int(m.group("patch") or 0),
        )

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self) -> str:
        return f"Version({self})"


@dataclass
class VersionRange:
    """Constraints like '>=1.0', '^1.2', '~1.2.3', '*', exact match."""

    raw: str = "*"

    def satisfied_by(self, version: Version) -> bool:
        if not self.raw or self.raw == "*":
            return True
        m = _VERSION_CONSTRAINT_RE.match(self.raw.strip())
        if not m:
            return version == Version.parse(self.raw)
        op = m.group("op") or "=="
        target = Version.parse(m.group("ver"))
        if op == "==" or op == "":
            return version == target
        if op == ">=":
            return version >= target
        if op == ">":
            return version > target
        if op == "<=":
            return version <= target
        if op == "<":
            return version < target
        if op == "^":
            return self._caret(version, target)
        if op == "~":
            return self._tilde(version, target)
        return False

    @staticmethod
    def _caret(ver: Version, target: Version) -> bool:
        if ver < target:
            return False
        if target.major == 0 and target.minor == 0:
            return ver.patch >= target.patch and ver.major == 0 and ver.minor == 0
        if target.major == 0:
            return ver.minor == target.minor and ver.patch >= target.patch and ver.major == 0
        return ver.major == target.major

    def _tilde(self, ver: Version, target: Version) -> bool:
        """npm tilde semantics.

        ``~1``      → >=1.0.0 <2.0.0
        ``~1.2``    → >=1.2.0 <1.3.0
        ``~1.2.3``  → >=1.2.3 <1.3.0
        """
        if ver < target:
            return False
        m = _VERSION_CONSTRAINT_RE.match(self.raw.strip())
        raw_ver = m.group("ver") if m else ""
        if len(raw_ver.split(".")) <= 1:
            return ver.major == target.major
        return ver.major == target.major and ver.minor == target.minor


@dataclass
class SkillSpec:
    """Canonical skill descriptor — independent of source or install state."""

    name: str
    version: Version = field(default_factory=lambda: Version(0, 0, 0))
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    mcp_required: list[str] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)   # name → constraint
    author: str = ""
    home_url: str = ""
    agent: dict[str, dict[str, Any]] = field(default_factory=dict)  # agent-specific overrides

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> SkillSpec:
        version = data.get("version")
        if isinstance(version, str):
            version = Version.parse(version)
        elif isinstance(version, (int, float)):
            version = Version.parse(str(version))
        else:
            version = Version(0, 0, 0)

        deps: dict[str, str] = {}
        raw_deps = data.get("dependencies", {}) or {}
        if isinstance(raw_deps, list):
            for item in raw_deps:
                if isinstance(item, str):
                    name_dep, _, constraint = item.partition("@")
                    deps[name_dep.strip()] = constraint.strip() or "*"
        elif isinstance(raw_deps, dict):
            deps = {str(k): str(v) for k, v in raw_deps.items()}

        agent: dict[str, dict[str, Any]] = {}
        raw_agent = data.get("agent", {}) or {}
        if isinstance(raw_agent, dict):
            for k, v in raw_agent.items():
                if isinstance(v, dict):
                    agent[str(k)] = {str(kk): vv for kk, vv in v.items()}

        return cls(
            name=name,
            version=version,
            description=str(data.get("description", "")).strip(),
            keywords=[str(k) for k in (data.get("keywords", []) or [])],
            mcp_required=[str(m) for m in (data.get("mcp_required", []) or [])],
            dependencies=deps,
            author=str(data.get("author", "")).strip(),
            home_url=str(data.get("home_url", "")).strip(),
            agent=agent,
        )

    def agent_override(self, agent_name: str) -> dict[str, Any]:
        """Return the per-agent override dict for ``agent_name`` (may be empty)."""
        return self.agent.get(agent_name, {})

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "version": str(self.version),
            "description": self.description,
            "keywords": self.keywords,
            "mcp_required": self.mcp_required,
        }
        if self.dependencies:
            d["dependencies"] = self.dependencies
        if self.author:
            d["author"] = self.author
        if self.home_url:
            d["home_url"] = self.home_url
        if self.agent:
            d["agent"] = self.agent
        return d


def parse_install_spec(raw: str) -> tuple[str, str]:
    """Parse ``dashboard@1.2.0`` → (name, version_req). Default version is '*'."""
    name, _, constraint = raw.partition("@")
    return name.strip(), constraint.strip() or "*"
