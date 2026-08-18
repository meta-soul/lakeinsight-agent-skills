from __future__ import annotations

from lakeinsight.source.github import _parse_manifest_yaml, _parse_tag_version, GitHubSource
from lakeinsight.spec import SkillSpec, Version


def test_parse_tag_version():
    assert str(_parse_tag_version("v1.2.0")) == "1.2.0"
    assert str(_parse_tag_version("1.2.0")) == "1.2.0"
    assert _parse_tag_version("release-3.0") is None
    assert _parse_tag_version("notatag") is None


def test_parse_manifest_yaml():
    raw = (
        "manifest_version: 1\n"
        "skills:\n"
        "  bi-task:\n"
        "    version: 1.0.0\n"
        "    description: foo\n"
        "    keywords: [a, b]\n"
        "    mcp_required: [m1]\n"
    )
    specs = _parse_manifest_yaml(raw)
    assert "bi-task" in specs
    assert str(specs["bi-task"].version) == "1.0.0"
    assert specs["bi-task"].description == "foo"
    assert specs["bi-task"].keywords == ["a", "b"]


def test_parse_manifest_yaml_invalid():
    assert _parse_manifest_yaml("not: [valid") == {}
    assert _parse_manifest_yaml("") == {}
    assert _parse_manifest_yaml("just a string") == {}


def _seed_cache(s, sha):
    clone_dir = s._cache_root / "clones" / "heads" / "main"
    (clone_dir / "skills").mkdir(parents=True)
    sha_file = s._cache_root / "clones" / "heads-main.sha"
    sha_file.parent.mkdir(parents=True, exist_ok=True)
    sha_file.write_text(sha, encoding="utf-8")
    return clone_dir


def test_fetch_cache_reuses_when_sha_unchanged(tmp_path, monkeypatch):
    s = GitHubSource("o", "r")
    s._cache_root = tmp_path / "cache"
    _seed_cache(s, "abc123")

    monkeypatch.setattr(s, "_remote_sha", lambda ref, kind: "abc123")
    calls: list[str] = []
    monkeypatch.setattr(s, "_git_clone", lambda ref, dest: calls.append(ref))

    top = s._fetch("main", "heads")
    assert top.name == "main"
    assert calls == []  # SHA 一致，不重新 clone


def test_fetch_cache_reclones_when_sha_changed(tmp_path, monkeypatch):
    s = GitHubSource("o", "r")
    s._cache_root = tmp_path / "cache"
    _seed_cache(s, "old-sha")

    monkeypatch.setattr(s, "_remote_sha", lambda ref, kind: "new-sha")
    calls: list[str] = []

    def fake_clone(ref, dest):
        calls.append(ref)
        dest.mkdir(parents=True, exist_ok=True)  # 模拟 clone 创建目录

    monkeypatch.setattr(s, "_git_clone", fake_clone)

    top = s._fetch("main", "heads")
    assert top.name == "main"
    assert calls != []  # SHA 变了，重新 clone
    sha_file = s._cache_root / "clones" / "heads-main.sha"
    assert sha_file.read_text(encoding="utf-8").strip() == "new-sha"


def test_fetch_cache_keeps_when_sha_unreachable(tmp_path, monkeypatch):
    s = GitHubSource("o", "r")
    s._cache_root = tmp_path / "cache"
    _seed_cache(s, "abc123")

    monkeypatch.setattr(s, "_remote_sha", lambda ref, kind: "")
    calls: list[str] = []
    monkeypatch.setattr(s, "_git_clone", lambda ref, dest: calls.append(ref))

    top = s._fetch("main", "heads")
    assert top.name == "main"
    assert calls == []  # 拿不到远程 SHA，降级用缓存


def _boom(ref, kind):
    raise AssertionError("list_versions 不应 clone")


def test_list_versions_prefers_manifest(tmp_path, monkeypatch):
    s = GitHubSource("o", "r")
    s._cache_root = tmp_path / "cache"
    spec = SkillSpec.from_dict("bi-task", {"version": "1.2.0"})
    monkeypatch.setattr(s, "_fetch_manifest_specs", lambda: {"bi-task": spec})
    monkeypatch.setattr(s, "_fetch_tags", lambda: [])
    monkeypatch.setattr(s, "_local_for", _boom)

    versions = s.list_versions("bi-task")
    assert [str(v) for v in versions] == ["1.2.0"]


def test_list_versions_from_tags_when_no_manifest(tmp_path, monkeypatch):
    s = GitHubSource("o", "r")
    s._cache_root = tmp_path / "cache"
    monkeypatch.setattr(s, "_fetch_manifest_specs", lambda: {})
    monkeypatch.setattr(s, "_fetch_tags", lambda: ["v1.0.0", "v1.1.0"])
    monkeypatch.setattr(s, "_local_for", _boom)

    versions = s.list_versions("bi-task")
    assert [str(v) for v in versions] == ["1.0.0", "1.1.0"]


def test_list_versions_falls_back_to_clone(tmp_path, monkeypatch):
    s = GitHubSource("o", "r")
    s._cache_root = tmp_path / "cache"
    monkeypatch.setattr(s, "_fetch_manifest_specs", lambda: {})
    monkeypatch.setattr(s, "_fetch_tags", lambda: [])

    class FakeLocal:
        def list_versions(self, name):
            return [Version(1, 0, 0)]

    monkeypatch.setattr(s, "_local_for", lambda ref, kind: FakeLocal())

    versions = s.list_versions("bi-task")
    assert [str(v) for v in versions] == ["1.0.0"]
