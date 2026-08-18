"""Install verification — confirm an installed skill is discoverable by its agent.

Files being present does not guarantee an agent will discover them (e.g. a skill
copied to the wrong directory, or a Cursor rule that never matches).  This module
wraps the per-agent checks and produces a uniform result.
"""

from __future__ import annotations

from typing import Any

from . import logger
from .agents import AgentAdapter, get_adapter

LOG = logger.LOG


def verify_agent_skill(
    agent: str,
    skill_name: str,
    target_dir: Any,
    spec: Any = None,
) -> dict[str, Any]:
    """Verify that ``agent`` can discover ``skill_name`` installed at ``target_dir``.

    Returns a dict with at least ``installed`` and ``discoverable`` booleans.
    """
    adapter: AgentAdapter = get_adapter(agent)
    result = adapter.verify(target_dir, skill_name, spec)
    return {
        "agent": agent,
        "skill": skill_name,
        "installed": bool(result.get("installed", False)),
        "discoverable": bool(result.get("discoverable", False)),
        "detail": result.get("detail", ""),
    }


def verify_all(
    installations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Verify a list of installation records (each with agent/skill/path)."""
    from pathlib import Path

    results: list[dict[str, Any]] = []
    for inst in installations:
        path = inst.get("path")
        if not path:
            results.append({
                "agent": inst.get("agent"),
                "skill": inst.get("skill"),
                "installed": False,
                "discoverable": False,
                "detail": "缺少 path",
            })
            continue
        results.append(
            verify_agent_skill(
                agent=inst.get("agent", ""),
                skill_name=inst.get("skill", ""),
                target_dir=Path(path).parent,
                spec=None,
            )
        )
    return results
