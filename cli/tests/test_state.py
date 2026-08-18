from __future__ import annotations

from lakeinsight.spec import Version
from lakeinsight.state import (
    Installation,
    InstalledSkill,
    get_installed_skills,
    make_installation_id,
    remove_installation,
    set_installed_skill,
)


def test_installation_id_stable_and_unique():
    a = make_installation_id("opencode", "global", "", "bi-task")
    b = make_installation_id("opencode", "global", "", "bi-task")
    assert a == b
    assert len(a) == 8
    c = make_installation_id("opencode", "project", "/repo", "bi-task")
    assert a != c


def test_installation_roundtrip():
    i = Installation(id="x", agent="opencode", scope="project", path="/p", root="/r", slug="r", resolver="detected")
    j = Installation.from_dict(i.to_dict())
    assert j.id == "x"
    assert j.agent == "opencode"
    assert j.root == "/r"
    assert j.slug == "r"
    assert j.resolver == "detected"


def test_legacy_install_path_migration(tmp_path, monkeypatch):
    state = tmp_path / "state.yaml"
    state.write_text(
        "installed:\n  foo:\n    version: 1.0.0\n    install_path: /old/foo\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("lakeinsight.state.STATE_PATH", state)
    foo = get_installed_skills()["foo"]
    assert foo.installations[0].agent == "custom"
    assert foo.installations[0].path == "/old/foo"


def test_remove_installation_drops_empty_skill(tmp_path, monkeypatch):
    state = tmp_path / "state.yaml"
    monkeypatch.setattr("lakeinsight.state.STATE_PATH", state)
    entry = InstalledSkill(
        name="foo",
        version=Version(1, 0, 0),
        installations=[
            Installation(id="a", agent="opencode", scope="global", path="/p1"),
            Installation(id="b", agent="claude-code", scope="global", path="/p2"),
        ],
    )
    set_installed_skill(entry)

    remove_installation("foo", "a")
    remaining = get_installed_skills()["foo"].installations
    assert [i.id for i in remaining] == ["b"]

    remove_installation("foo", "b")
    assert "foo" not in get_installed_skills()
