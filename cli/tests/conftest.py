"""Shared pytest fixtures.

The ``isolated`` fixture redirects ``Path.home()``, the install state file and
the download cache to a temp dir so tests never touch the real ``~/.lakeinsight``
or agent skill directories.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME / state / cache / config into a temporary directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr("lakeinsight.state.STATE_PATH", home / ".lakeinsight" / "state.yaml")
    monkeypatch.setattr("lakeinsight.skill.CACHE_DIR", home / ".lakeinsight" / "cache")
    monkeypatch.setattr(
        "lakeinsight.source.resolver._CONFIG_PATH",
        home / ".lakeinsight" / "config.yaml",
    )
    return home
