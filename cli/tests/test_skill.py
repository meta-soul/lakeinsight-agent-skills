from __future__ import annotations

import yaml
import pytest

from lakeinsight.errors import SkillAlreadyInstalledError
from lakeinsight.skill import install_skill, remove_skill, update_skill
from lakeinsight.source.local import LocalSource
from lakeinsight.state import get_installed_skills


def _make_skill(root, name, version, **extra):
    d = root / name
    d.mkdir(parents=True)
    fm = {"version": version, "description": f"skill {name}"}
    fm.update(extra)
    (d / "SKILL.md").write_text(
        f"---\n{yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)}---\n\n# {name}\n",
        encoding="utf-8",
    )


def _src(tmp_path):
    skills = tmp_path / "skills"
    _make_skill(skills, "alpha", "1.0.0")
    return LocalSource(root=skills)


def test_install_to_agent(isolated, tmp_path):
    src = _src(tmp_path)
    result = install_skill(src, "alpha", agents=["opencode"], scope="global")
    assert result["name"] == "alpha"
    inst = result["installations"][0]
    assert inst.agent == "opencode"
    assert inst.scope == "global"
    assert inst.path.endswith(".config/opencode/skills/alpha".replace("/", "\\")) or \
        inst.path.endswith(".config/opencode/skills/alpha")

    state = get_installed_skills()["alpha"]
    assert len(state.installations) == 1


def test_install_multi_agent(isolated, tmp_path):
    src = _src(tmp_path)
    result = install_skill(src, "alpha", agents=["opencode", "claude-code"], scope="global")
    agents = [i.agent for i in result["installations"]]
    assert set(agents) == {"opencode", "claude-code"}
    assert len(get_installed_skills()["alpha"].installations) == 2


def test_install_no_agent_raises(isolated, tmp_path):
    src = _src(tmp_path)
    with pytest.raises(Exception) as exc:
        install_skill(src, "alpha", agents=None, scope="global")
    assert "agent" in str(exc.value)


def test_install_duplicate_raises(isolated, tmp_path):
    src = _src(tmp_path)
    install_skill(src, "alpha", agents=["opencode"], scope="global")
    with pytest.raises(SkillAlreadyInstalledError):
        install_skill(src, "alpha", agents=["opencode"], scope="global")


def test_install_force_overwrites(isolated, tmp_path):
    src = _src(tmp_path)
    install_skill(src, "alpha", agents=["opencode"], scope="global")
    result = install_skill(src, "alpha", agents=["opencode"], scope="global", force=True)
    assert result["installations"][0].agent == "opencode"


def test_install_dependencies_recursive(isolated, tmp_path):
    skills = tmp_path / "skills"
    _make_skill(skills, "alpha", "1.0.0")
    _make_skill(skills, "beta", "2.0.0", dependencies={"alpha": "*"})
    src = LocalSource(root=skills)

    install_skill(src, "beta", agents=["opencode"], scope="global")
    installed = get_installed_skills()
    assert "beta" in installed and "alpha" in installed


def test_remove_single_agent(isolated, tmp_path):
    src = _src(tmp_path)
    install_skill(src, "alpha", agents=["opencode", "claude-code"], scope="global")
    remove_skill("alpha", agent="opencode")
    state = get_installed_skills()["alpha"]
    assert [i.agent for i in state.installations] == ["claude-code"]


def test_remove_all(isolated, tmp_path):
    src = _src(tmp_path)
    install_skill(src, "alpha", agents=["opencode", "claude-code"], scope="global")
    remove_skill("alpha")
    assert "alpha" not in get_installed_skills()


def test_install_project_scope(isolated, tmp_path):
    src = _src(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    result = install_skill(
        src, "alpha", agents=["opencode"], scope="project", project_root=repo
    )
    inst = result["installations"][0]
    assert inst.scope == "project"
    assert str(repo) in inst.path
    assert inst.slug == "repo"


def test_update_multiple_project_roots(isolated, tmp_path):
    src = _src(tmp_path)
    repo1 = tmp_path / "repo1"
    repo1.mkdir()
    repo2 = tmp_path / "repo2"
    repo2.mkdir()

    install_skill(src, "alpha", agents=["opencode"], scope="project", project_root=repo1)
    install_skill(src, "alpha", agents=["opencode"], scope="project", project_root=repo2)
    assert len(get_installed_skills()["alpha"].installations) == 2

    update_skill(src, "alpha")
    state = get_installed_skills()["alpha"]
    assert len(state.installations) == 2
    roots = sorted(i.root for i in state.installations)
    assert roots == sorted([str(repo1), str(repo2)])
