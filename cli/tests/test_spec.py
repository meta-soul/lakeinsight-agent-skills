from __future__ import annotations

from lakeinsight.spec import SkillSpec, Version, VersionRange, parse_install_spec


def test_version_parse():
    assert str(Version.parse("1.2.3")) == "1.2.3"
    assert str(Version.parse("1.2")) == "1.2.0"
    assert str(Version.parse("1")) == "1.0.0"
    assert str(Version.parse("garbage")) == "0.0.0"


def test_version_order():
    assert Version(1, 2, 0) < Version(1, 2, 1)
    assert Version(2, 0, 0) > Version(1, 9, 9)
    assert Version(1, 0, 0) == Version(1, 0, 0)


def test_version_range_caret():
    assert VersionRange("^1.2").satisfied_by(Version(1, 5, 0))
    assert VersionRange("^1.2").satisfied_by(Version(1, 2, 0))
    assert not VersionRange("^1.2").satisfied_by(Version(2, 0, 0))
    assert not VersionRange("^1.2").satisfied_by(Version(1, 1, 9))


def test_version_range_tilde():
    assert VersionRange("~1.2.3").satisfied_by(Version(1, 2, 9))
    assert not VersionRange("~1.2.3").satisfied_by(Version(1, 3, 0))


def test_version_range_ge():
    assert VersionRange(">=1.0").satisfied_by(Version(1, 0, 0))
    assert VersionRange(">=1.0").satisfied_by(Version(2, 5, 0))
    assert not VersionRange(">=1.0").satisfied_by(Version(0, 9, 0))


def test_version_range_exact():
    assert VersionRange("1.2.0").satisfied_by(Version(1, 2, 0))
    assert not VersionRange("1.2.0").satisfied_by(Version(1, 2, 1))


def test_skill_spec_agent_metadata():
    spec = SkillSpec.from_dict("x", {
        "version": "1.0.0",
        "agent": {"cursor": {"globs": ["**/*.sql"], "alwaysApply": False}},
    })
    assert spec.agent_override("cursor") == {"globs": ["**/*.sql"], "alwaysApply": False}
    assert spec.agent_override("opencode") == {}


def test_skill_spec_dependencies_list_and_dict():
    a = SkillSpec.from_dict("x", {"dependencies": ["alpha@1.0", "beta@^2.0"]})
    assert a.dependencies == {"alpha": "1.0", "beta": "^2.0"}
    b = SkillSpec.from_dict("x", {"dependencies": {"alpha": ">=1.0"}})
    assert b.dependencies == {"alpha": ">=1.0"}


def test_skill_spec_roundtrip():
    spec = SkillSpec.from_dict("x", {
        "version": "1.2.3",
        "description": "hi",
        "agent": {"cursor": {"globs": ["**/*.py"]}},
    })
    data = spec.to_dict()
    spec2 = SkillSpec.from_dict("x", data)
    assert spec2.version == Version(1, 2, 3)
    assert spec2.agent == {"cursor": {"globs": ["**/*.py"]}}


def test_parse_install_spec():
    assert parse_install_spec("dashboard@1.2.0") == ("dashboard", "1.2.0")
    assert parse_install_spec("dashboard") == ("dashboard", "*")
