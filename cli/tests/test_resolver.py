from __future__ import annotations

import pytest

from lakeinsight.errors import LakeInsightError
from lakeinsight.source.github import GitHubSource
from lakeinsight.source.resolver import resolve_source, save_config


def test_resolve_default_is_official_repo_without_config(isolated):
    s = resolve_source(None)
    assert isinstance(s, GitHubSource)
    assert s.owner == "meta-soul"
    assert s.repo == "lakeinsight-agent-skills"


def test_resolve_default_from_config(isolated):
    save_config({"default_source": "github", "github": {"owner": "o", "repo": "r"}})
    s = resolve_source(None)
    assert isinstance(s, GitHubSource)
    assert s.owner == "o"
    assert s.repo == "r"


def test_resolve_shorthand_overrides_config(isolated):
    save_config({"default_source": "github", "github": {"owner": "o", "repo": "r"}})
    s = resolve_source("github:x/y@main")
    assert isinstance(s, GitHubSource)
    assert s.owner == "x"
    assert s.repo == "y"
    assert s.ref == "main"


def test_resolve_unknown_source_raises(isolated):
    with pytest.raises(LakeInsightError):
        resolve_source("local")


def test_resolve_unknown_source_raises_2(isolated):
    with pytest.raises(LakeInsightError):
        resolve_source("nonsense")
