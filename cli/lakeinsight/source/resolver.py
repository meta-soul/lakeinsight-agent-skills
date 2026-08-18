"""Source resolver — picks the right SkillSource at runtime.

Priority:  ``--source`` flag  →  ``~/.lakeinsight/config.yaml``  →  built-in default (official repo).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .. import logger
from ..config import (
    DEFAULT_GITHUB_OWNER,
    DEFAULT_GITHUB_REF,
    DEFAULT_GITHUB_REPO,
    LAKEINSIGHT_HOME,
)
from ..errors import LakeInsightError

LOG = logger.LOG

_CONFIG_PATH = LAKEINSIGHT_HOME / "config.yaml"
_DEFAULT_CONFIG: dict[str, Any] = {
    "default_source": "github",
    "github": {
        "owner": DEFAULT_GITHUB_OWNER,
        "repo": DEFAULT_GITHUB_REPO,
        "ref": DEFAULT_GITHUB_REF,
    },
}


def load_config(path: Path | None = None) -> dict[str, Any]:
    p = path or _CONFIG_PATH
    if not p.exists():
        return dict(_DEFAULT_CONFIG)
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception:
        return dict(_DEFAULT_CONFIG)
    if isinstance(data, dict):
        return data
    return dict(_DEFAULT_CONFIG)


def save_config(data: dict[str, Any], path: Path | None = None) -> None:
    p = path or _CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)


def resolve_source(source_name: str | None = None) -> "SkillSource":  # noqa: F821
    """Resolve the active SkillSource.

    ``source_name`` takes priority, then ``config.yaml``, then the built-in
    default (official repo).

    The ``github`` source accepts ``github:owner/repo[@ref]`` shorthand, e.g.
    ``--source github:lakeinsight/skills@main``.  Otherwise it reads the
    ``github`` section of ``~/.lakeinsight/config.yaml``.
    """
    name = source_name
    if name is None:
        config = load_config()
        name = config.get("default_source", "github")

    LOG.debug("resolving source: requested=%s resolved=%s", source_name, name)

    if name == "github" or name.startswith("github:"):
        from .github import GitHubSource

        config = load_config()
        gh = config.get("github", {}) or {}
        owner = gh.get("owner")
        repo = gh.get("repo")
        ref = gh.get("ref", "main")

        spec_part = name.split(":", 1)[1] if ":" in name else ""
        if spec_part:
            owner_repo, _, ref_part = spec_part.partition("@")
            if "/" in owner_repo:
                owner, repo = owner_repo.split("/", 1)
            if ref_part:
                ref = ref_part

        if not owner or not repo:
            raise LakeInsightError(
                "github 源需要配置 owner/repo：在 ~/.lakeinsight/config.yaml 的 "
                "github 段设置，或用 --source github:owner/repo[@ref]"
            )
        return GitHubSource(owner=owner, repo=repo, ref=ref)

    raise LakeInsightError(f"未知 source '{name}'，支持: github")
