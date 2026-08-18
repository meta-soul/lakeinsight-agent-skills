from __future__ import annotations

from pathlib import Path

import pytest

from lakeinsight.agents import (
    ClaudeCodeAdapter,
    CodexAdapter,
    CursorAdapter,
    OpenCodeAdapter,
    get_adapter,
)
from lakeinsight.errors import UnknownAgentError
from lakeinsight.spec import SkillSpec


def test_get_adapter_unknown():
    with pytest.raises(UnknownAgentError) as exc:
        get_adapter("nope")
    assert "nope" in str(exc.value)


def test_opencode_paths(isolated):
    a = OpenCodeAdapter()
    assert a.resolve_global_dir() == isolated / ".config" / "opencode" / "skills"
    assert a.resolve_project_dir(isolated / "repo") == isolated / "repo" / ".opencode" / "skills"


def test_claude_paths(isolated):
    a = ClaudeCodeAdapter()
    assert a.resolve_global_dir() == isolated / ".claude" / "skills"
    assert a.resolve_project_dir(isolated / "repo") == isolated / "repo" / ".claude" / "skills"


def test_codex_candidate_detection(isolated):
    a = CodexAdapter()
    # 无任何候选目录存在 → default（第一个候选）
    assert a.resolve_global_dir() == isolated / ".codex" / "skills"

    # existing > default
    (isolated / ".agents" / "skills").mkdir(parents=True)
    assert a.resolve_global_dir() == isolated / ".agents" / "skills"

    path, resolver = a.detected_global_dir()
    assert path == isolated / ".agents" / "skills"
    assert resolver == "detected"


def test_cursor_to_mdc(tmp_path):
    a = CursorAdapter()
    skill_dir = tmp_path / "s"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Generate dashboards\n---\n\n# Body\n",
        encoding="utf-8",
    )
    spec = SkillSpec.from_dict("dashboard", {
        "description": "Generate dashboards",
        "agent": {"cursor": {"globs": ["**/*.py"], "alwaysApply": True}},
    })
    content = a._to_mdc(skill_dir, "dashboard", spec)
    assert "description: Generate dashboards" in content
    assert "**/*.py" in content
    assert "alwaysApply: true" in content
    assert "# Body" in content


def test_cursor_to_mdc_defaults(tmp_path):
    a = CursorAdapter()
    skill_dir = tmp_path / "s"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: X\n---\n\n# Body\n",
        encoding="utf-8",
    )
    spec = SkillSpec.from_dict("d", {"description": "X"})
    content = a._to_mdc(skill_dir, "d", spec)
    # 未配置 globs 时默认 "**/*"，alwaysApply 默认 false
    assert "'**/*'" in content
    assert "alwaysApply: false" in content


def test_cursor_inline_references(tmp_path):
    a = CursorAdapter()
    skill_dir = tmp_path / "s"
    ref_dir = skill_dir / "references"
    ref_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: X\n---\n\n# Body\n\n详见 references/workflow.md\n",
        encoding="utf-8",
    )
    (ref_dir / "workflow.md").write_text("# Workflow 规范\n\n具体内容 ABC\n", encoding="utf-8")
    spec = SkillSpec.from_dict("d", {"description": "X"})
    content = a._to_mdc(skill_dir, "d", spec)
    # 引用的 references 内容被内联，避免断链
    assert "# Workflow 规范" in content
    assert "具体内容 ABC" in content


def test_cursor_inline_references_skips_missing(tmp_path):
    a = CursorAdapter()
    skill_dir = tmp_path / "s"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: X\n---\n\n# Body\n\n见 references/not-exist.md\n",
        encoding="utf-8",
    )
    spec = SkillSpec.from_dict("d", {"description": "X"})
    content = a._to_mdc(skill_dir, "d", spec)
    # 不存在的引用不内联，也不报错；正文仍在
    assert "# Body" in content
    assert "not-exist" in content  # 原引用行保留
