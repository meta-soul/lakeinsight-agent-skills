from __future__ import annotations

import pytest
from typer.testing import CliRunner

from lakeinsight.cli import app
from lakeinsight.source.local import LocalSource

runner = CliRunner()


@pytest.fixture
def local_source(monkeypatch):
    """让 CLI 测试走本地源，避免触发网络。"""
    monkeypatch.setattr(
        "lakeinsight.cli.resolve_source", lambda name=None: LocalSource()
    )


def test_install_unknown_agent_exit_code(isolated, local_source):
    result = runner.invoke(app, ["skill", "install", "bi-task", "--agent", "nope"])
    assert result.exit_code == 1
    assert "未知 agent" in result.output


def test_install_missing_agent_exit_code(isolated, local_source):
    result = runner.invoke(app, ["skill", "install", "bi-task"])
    assert result.exit_code == 1


def test_agents_command_runs(isolated):
    result = runner.invoke(app, ["skill", "agents"])
    assert result.exit_code == 0


def test_install_all_agents_no_agent_found(isolated, local_source):
    result = runner.invoke(app, ["skill", "install", "bi-task", "--all-agents"])
    assert result.exit_code == 1
    assert "未探测到任何" in result.output


def test_install_all_agents_detected(isolated, local_source):
    (isolated / ".config" / "opencode" / "skills").mkdir(parents=True)
    result = runner.invoke(app, ["skill", "install", "bi-task", "--all-agents"])
    assert result.exit_code == 0
    assert "opencode" in result.output
