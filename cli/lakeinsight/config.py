"""Path and configuration constants for the lakeinsight CLI."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent        # .../cli/lakeinsight/
_REPO_CANDIDATE = PACKAGE_ROOT.parents[1]              # .../cli/lakeinsight/ → repo root
# Handle the case where the package is installed as a wheel (site-packages/lakeinsight/).
REPO_ROOT = _REPO_CANDIDATE if (_REPO_CANDIDATE / "skills").is_dir() else Path.cwd()

MANIFEST_VERSION = 1

# 官方 skill 仓库（默认 source，用户无需每次指定 --source）
DEFAULT_GITHUB_OWNER = "meta-soul"
DEFAULT_GITHUB_REPO = "lakeinsight-agent-skills"
DEFAULT_GITHUB_REF = "main"

HOME = Path.home()
LAKEINSIGHT_HOME = HOME / ".lakeinsight"
STATE_PATH = LAKEINSIGHT_HOME / "state.yaml"
CONFIG_PATH = LAKEINSIGHT_HOME / "config.yaml"

DEFAULT_INSTALL_DIR = LAKEINSIGHT_HOME / "skills"
CACHE_DIR = LAKEINSIGHT_HOME / "cache"
ENV_INSTALL_DIR = "LAKEINSIGHT_SKILLS_DIR"


def get_install_dir() -> Path:
    """Return the skill install directory.

    Priority: --install_dir option > $LAKEINSIGHT_SKILLS_DIR > ~/.lakeinsight/skills.
    """
    override = os.environ.get(ENV_INSTALL_DIR)
    if override:
        return Path(override).expanduser()
    return DEFAULT_INSTALL_DIR


def get_project_root(start: Path | None = None, explicit: Path | None = None) -> Path:
    """Resolve the project root for ``project`` scope installs.

    Priority: ``explicit`` > nearest ``.git`` ancestor of ``start`` > ``start``/cwd.
    """
    if explicit is not None:
        return explicit.resolve()
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return cur
