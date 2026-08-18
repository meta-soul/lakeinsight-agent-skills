"""Agent adapters — map an agent to its skill directory and install method.

Each agent has different conventions for where skills live and how they are
installed.  The :class:`AgentAdapter` abstraction captures those differences so
the core install flow stays agent-agnostic.

Three adapter kinds:

- :class:`CopyAdapter`     — copy the ``SKILL.md`` directory verbatim (Claude Code, OpenCode, Copilot).
- :class:`DetectAdapter`   — probe candidate directories, prefer the one that already exists (Codex).
- :class:`RuleAdapter`     — transform ``SKILL.md`` into a rule file instead of copying (Cursor).

The registry ``AGENTS`` maps an agent name to its adapter instance.
"""

from __future__ import annotations

import re
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from . import logger
from .errors import UnknownAgentError

LOG = logger.LOG


class AgentAdapter(ABC):
    """Base adapter for a coding agent."""

    name: str = "base"

    @abstractmethod
    def resolve_global_dir(self) -> Path:
        """Return the global (user-level) skill directory for this agent."""

    @abstractmethod
    def resolve_project_dir(self, root: Path) -> Path:
        """Return the project-level skill directory under ``root``."""

    def resolve_dir(self, scope: str, root: Path | None = None) -> Path:
        """Return the install directory for ``scope`` (global/project)."""
        if scope == "project":
            if root is None:
                raise ValueError("project scope 需要提供 project root")
            return self.resolve_project_dir(root)
        return self.resolve_global_dir()

    @abstractmethod
    def install(self, skill_dir: Path, target_dir: Path, skill_name: str, spec: Any) -> Path:
        """Install ``skill_dir`` into ``target_dir``; return the final artifact path.

        For copy adapters the artifact is ``target_dir/<skill_name>``; for rule
        adapters it is ``target_dir/<skill_name>.mdc``.
        """

    @abstractmethod
    def verify(self, target_dir: Path, skill_name: str, spec: Any) -> dict[str, Any]:
        """Verify the agent can discover the installed skill; return a result dict."""


class CopyAdapter(AgentAdapter):
    """Copy the whole ``SKILL.md`` directory into the agent's skill dir."""

    def install(self, skill_dir: Path, target_dir: Path, skill_name: str, spec: Any) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / skill_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill_dir, target)
        LOG.debug("copied %s → %s", skill_dir, target)
        return target

    def verify(self, target_dir: Path, skill_name: str, spec: Any) -> dict[str, Any]:
        target = target_dir / skill_name / "SKILL.md"
        return _verify_skill_md(target)


class DetectAdapter(CopyAdapter):
    """Copy adapter whose global dir is detected from candidate paths.

    The first existing candidate wins; if none exists, the first candidate is
    returned (existing > default).
    """

    candidates: list[str] = []

    def candidate_paths(self) -> list[Path]:
        return [Path.home() / c for c in self.candidates]

    def resolve_global_dir(self) -> Path:
        path, _ = self.detected_global_dir()
        return path

    def detected_global_dir(self) -> tuple[Path, str]:
        """Return (path, resolver) where resolver is 'detected' or 'default'."""
        for p in self.candidate_paths():
            if p.exists():
                return p, "detected"
        return self.candidate_paths()[0], "default"


class RuleAdapter(AgentAdapter):
    """Transform a ``SKILL.md`` into a ``.mdc`` rule file (Cursor)."""

    rule_suffix = ".mdc"

    def resolve_global_dir(self) -> Path:
        return Path.home() / ".cursor" / "rules"

    def resolve_project_dir(self, root: Path) -> Path:
        return root / ".cursor" / "rules"

    def install(self, skill_dir: Path, target_dir: Path, skill_name: str, spec: Any) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{skill_name}{self.rule_suffix}"
        content = self._to_mdc(skill_dir, skill_name, spec)
        target.write_text(content, encoding="utf-8")
        LOG.debug("generated rule %s", target)
        return target

    def _to_mdc(self, skill_dir: Path, skill_name: str, spec: Any) -> str:
        skill_md = skill_dir / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8") if skill_md.exists() else ""

        body = text
        description = getattr(spec, "description", "") or ""
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                body = text[end + 4 :].lstrip("\n")
                try:
                    import yaml

                    fm = yaml.safe_load(text[3:end].strip()) or {}
                    description = str(fm.get("description", description)).strip()
                except Exception:
                    pass

        # 内联展开 references/xxx.md 引用，避免单文件 .mdc 相对路径断链
        body = self._inline_references(skill_dir, body)

        override = spec.agent_override(self.name) if hasattr(spec, "agent_override") else {}
        globs = override.get("globs", ["**/*"])
        always_apply = bool(override.get("alwaysApply", False))

        import yaml

        front = {
            "description": description,
            "globs": list(globs),
            "alwaysApply": always_apply,
        }
        return f"---\n{yaml.safe_dump(front, allow_unicode=True, sort_keys=False).strip()}\n---\n\n{body}"

    @staticmethod
    def _inline_references(skill_dir: Path, body: str) -> str:
        """Append the contents of referenced ``references/*.md`` files to ``body``.

        Copy-based agents keep the whole skill directory (references intact), but a
        Cursor rule is a single ``.mdc`` file — relative ``references/...`` links
        would dangle.  We inline any referenced file that actually exists.
        """
        ref_dir = skill_dir / "references"
        if not ref_dir.is_dir():
            return body
        pattern = re.compile(r"references/([\w\-\.]+\.md)")
        seen: set[str] = set()
        extra: list[str] = []
        for m in pattern.finditer(body):
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            ref_path = ref_dir / name
            if ref_path.exists():
                content = ref_path.read_text(encoding="utf-8").strip()
                extra.append(f"## {name}\n\n{content}")
        if not extra:
            return body
        return body.rstrip() + "\n\n---\n\n" + "\n\n---\n\n".join(extra)

    def verify(self, target_dir: Path, skill_name: str, spec: Any) -> dict[str, Any]:
        target = target_dir / f"{skill_name}{self.rule_suffix}"
        if not target.exists():
            return {"installed": False, "discoverable": False, "detail": f"rule 不存在: {target}"}
        return {"installed": True, "discoverable": True, "detail": str(target)}


# ── concrete agents ───────────────────────────────────────────────────────────


class ClaudeCodeAdapter(CopyAdapter):
    name = "claude-code"

    def resolve_global_dir(self) -> Path:
        return Path.home() / ".claude" / "skills"

    def resolve_project_dir(self, root: Path) -> Path:
        return root / ".claude" / "skills"


class OpenCodeAdapter(CopyAdapter):
    name = "opencode"

    def resolve_global_dir(self) -> Path:
        return Path.home() / ".config" / "opencode" / "skills"

    def resolve_project_dir(self, root: Path) -> Path:
        return root / ".opencode" / "skills"


class CodexAdapter(DetectAdapter):
    name = "codex"
    candidates = [".codex/skills", ".agents/skills"]

    def resolve_project_dir(self, root: Path) -> Path:
        return root / ".codex" / "skills"


class CopilotAdapter(CopyAdapter):
    name = "copilot"

    def resolve_global_dir(self) -> Path:
        return Path.home() / ".copilot" / "skills"

    def resolve_project_dir(self, root: Path) -> Path:
        return root / ".github" / "skills"


class CursorAdapter(RuleAdapter):
    name = "cursor"


AGENTS: dict[str, AgentAdapter] = {
    a.name: a
    for a in (
        ClaudeCodeAdapter(),
        OpenCodeAdapter(),
        CodexAdapter(),
        CopilotAdapter(),
        CursorAdapter(),
    )
}


def get_adapter(agent: str) -> AgentAdapter:
    """Return the adapter for ``agent`` or raise UnknownAgentError."""
    a = AGENTS.get(agent)
    if a is None:
        raise UnknownAgentError(agent, sorted(AGENTS))
    return a


def detect_agents() -> list[str]:
    """Return the names of agents whose global skill dir already exists."""
    found: list[str] = []
    for name, adapter in AGENTS.items():
        try:
            if adapter.resolve_global_dir().exists():
                found.append(name)
        except Exception:
            continue
    return found


def _verify_skill_md(skill_md_path: Path) -> dict[str, Any]:
    """Verify a copied skill: SKILL.md exists and frontmatter parses."""
    if not skill_md_path.exists():
        return {
            "installed": False,
            "discoverable": False,
            "detail": f"SKILL.md 不存在: {skill_md_path}",
        }
    text = skill_md_path.read_text(encoding="utf-8")
    valid = text.strip().startswith("---")
    if valid:
        try:
            import yaml

            end = text.find("\n---", 3)
            if end != -1:
                yaml.safe_load(text[3:end].strip())
        except Exception:
            valid = False
    return {
        "installed": True,
        "discoverable": valid,
        "detail": str(skill_md_path),
    }
