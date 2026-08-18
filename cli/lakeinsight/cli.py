"""lakeinsight CLI: manage agent skill lifecycle.

Commands:
    lakeinsight skill list    [--source SRC]
    lakeinsight skill info    <name> [--source SRC]
    lakeinsight skill search  <keyword> [--source SRC]
    lakeinsight skill install <name[@ver]> [--source SRC] [--install-dir PATH] [--force] [--no-deps]
    lakeinsight skill remove  <name>
    lakeinsight skill update  <name> [--source SRC]
    lakeinsight dev sync
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Force UTF-8 on Windows consoles to avoid GBK encode errors for bullets/checks.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__
from . import logger
from .agents import detect_agents
from .errors import LakeInsightError
from .source import SkillSource
from .source.resolver import resolve_source
from .skill import (
    get_skill_info,
    install_skill,
    list_skills,
    remove_skill,
    search_skills,
    sync_manifest,
    update_skill,
)

app = typer.Typer(
    name="lakeinsight",
    help="LakeInsight agent skills 生命周期管理",
    no_args_is_help=True,
)
skill_app = typer.Typer(
    name="skill",
    help="管理 agent skills 的安装/搜索/信息",
    no_args_is_help=True,
)
dev_app = typer.Typer(
    name="dev",
    help="开发者工具（sync manifest 等）",
    no_args_is_help=True,
)
app.add_typer(skill_app)
app.add_typer(dev_app)

console = Console()


def _get_source(source_name: str | None = None) -> SkillSource:
    return resolve_source(source_name)


# ── top-level callback ───────────────────────────────────────────────────────


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="显示版本并退出"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示详细日志"),
    debug: bool = typer.Option(False, "--debug", help="显示调试日志"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Skill 源: github"),
) -> None:
    if debug:
        logger.setup_logging(2)
    elif verbose:
        logger.setup_logging(1)
    else:
        logger.setup_logging(0)

    ctx.ensure_object(dict)
    ctx.obj["_source"] = source

    if version:
        console.print(f"lakeinsight {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


# ── helpers ──────────────────────────────────────────────────────────────────


def _trim_desc(text: str, limit: int = 30) -> str:
    summary = next((line.strip() for line in text.splitlines() if line.strip()), "-")
    if len(summary) > limit:
        cut = limit
        for sep in ("。", "；", "，", ","):
            idx = summary.find(sep, 10, limit)
            if idx != -1:
                cut = idx + 1
                break
        summary = summary[:cut] + "…"
    return summary


# ── skill group callback ────────────────────────────────────────────────────


@skill_app.callback(invoke_without_command=True)
def skill_main(
    ctx: typer.Context,
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Skill 源: github"),
) -> None:
    ctx.ensure_object(dict)
    if source is not None:
        ctx.obj["_source"] = source


# ── skill list ───────────────────────────────────────────────────────────────


@skill_app.command("list")
def skill_list(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示安装路径等详细信息"),
) -> None:
    """列出所有可用的 skill 及其安装状态。"""
    source = _get_source(ctx.obj.get("_source"))
    try:
        items = list_skills(source)
    except LakeInsightError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1)
    if not items:
        console.print("[yellow]没有发现任何 skill。[/yellow]")
        return

    table = Table(title="LakeInsight Agent Skills")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Version", style="magenta")
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Description", overflow="fold")
    if verbose:
        table.add_column("Installations", style="dim")

    for item in items:
        spec = item["spec"]
        status = "[green]installed[/green]" if item["installed"] else "[dim]not installed[/dim]"
        summary = _trim_desc(spec.description)
        if verbose:
            installs = item.get("installations") or []
            if installs:
                cols = ", ".join(f"{i.agent}/{i.scope}" for i in installs)
            else:
                cols = "-"
            table.add_row(spec.name, str(spec.version), status, summary, cols)
        else:
            table.add_row(spec.name, str(spec.version), status, summary)

    console.print(table)


# ── skill info ───────────────────────────────────────────────────────────────


@skill_app.command("info")
def skill_info(
    ctx: typer.Context,
    name: str,
) -> None:
    """查看某个 skill 的详细信息（版本、依赖、关键词等）。"""
    source = _get_source(ctx.obj.get("_source"))
    try:
        info = get_skill_info(source, name)
    except LakeInsightError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1)

    spec = info["spec"]
    lines: list[str] = [
        f"[bold cyan]Name:[/bold cyan]           {spec.name}",
        f"[bold magenta]Version:[/bold magenta]        {spec.version}",
    ]
    if spec.author:
        lines.append(f"[bold]Author:[/bold]          {spec.author}")
    if spec.home_url:
        lines.append(f"[bold]Home:[/bold]            {spec.home_url}")
    lines.append("")
    lines.append(f"[bold]Description:[/bold]     {spec.description}")

    if spec.keywords:
        lines.append(f"[bold]Keywords:[/bold]        {', '.join(spec.keywords)}")
    if spec.mcp_required:
        lines.append(f"[bold]MCP Required:[/bold]    {', '.join(spec.mcp_required)}")
    if spec.dependencies:
        deps = ", ".join(f"{k}@{v}" for k, v in spec.dependencies.items())
        lines.append(f"[bold]Dependencies:[/bold]    {deps}")

    versions_str = ", ".join(info["available_versions"])
    lines.append(f"[bold]Available Versions:[/bold] {versions_str}")

    if info["installed"]:
        lines.append("")
        lines.append(f"[bold green]Installed:[/bold green]       v{info['installed_version']}")
        lines.append(f"[bold]Installed At:[/bold]    {info['installed_at']}")
        for inst in info.get("installations") or []:
            scope = f"{inst.scope}" + (f" @ {inst.slug}" if inst.slug else "")
            lines.append(f"[bold]  -[/bold] {inst.agent} [{scope}]: {inst.path}")
    else:
        lines.append("")
        lines.append("[dim]Not installed[/dim]")

    md = Text.from_markup("\n".join(lines))
    console.print(Panel(md, title=f"{spec.name} — Skill Info", border_style="cyan"))


# ── skill search ─────────────────────────────────────────────────────────────


@skill_app.command("search")
def skill_search(
    ctx: typer.Context,
    query: str,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示描述详情"),
) -> None:
    """按关键词搜索 skill（匹配名称、描述、关键词）。"""
    source = _get_source(ctx.obj.get("_source"))
    try:
        results = search_skills(source, query)
        installed_map = {it["spec"].name: it for it in list_skills(source)}
    except LakeInsightError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1)
    if not results:
        console.print(f"[yellow]未找到匹配 '{query}' 的 skill。[/yellow]")
        return

    table = Table(title=f"搜索 '{query}' 的结果")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Version", style="magenta")
    table.add_column("Status", justify="center", no_wrap=True)
    if verbose:
        table.add_column("Description")

    for spec in results:
        item = installed_map.get(spec.name, {})
        status = "[green]installed[/green]" if item.get("installed") else "[dim]-[/dim]"
        if verbose:
            table.add_row(spec.name, str(spec.version), status, _trim_desc(spec.description, 60))
        else:
            table.add_row(spec.name, str(spec.version), status)

    console.print(table)


# ── skill install ────────────────────────────────────────────────────────────


@skill_app.command("install")
def skill_install(
    ctx: typer.Context,
    name: str,
    install_dir: Optional[Path] = typer.Option(None, "--install-dir", "-d", help="覆盖安装目录（custom 安装）"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="安装到的 agent（逗号分隔，如 opencode,claude-code）"),
    all_agents: bool = typer.Option(False, "--all-agents", help="安装到所有已探测的 agent"),
    scope: str = typer.Option("global", "--scope", help="作用域: global / project"),
    project_root: Optional[Path] = typer.Option(None, "--project-root", help="project scope 的项目根目录"),
    force: bool = typer.Option(False, "--force", "-f", help="已安装时强制重新安装"),
    no_deps: bool = typer.Option(False, "--no-deps", help="不自动安装依赖"),
    source: str = typer.Option("", "--source", "-s", help="Skill 源（覆盖全局设置）"),
) -> None:
    """安装 skill：从源下载并安装到指定 agent / scope。

    name 格式:  <skill>[@version]  如  dashboard  或  dashboard@1.2.0
    """
    resolved = _get_source(source or ctx.obj.get("_source"))
    if all_agents:
        agents = detect_agents()
        if not agents:
            console.print("[red]错误:[/red] 未探测到任何已安装的 agent，无法使用 --all-agents")
            raise typer.Exit(code=1)
    else:
        agents = [a.strip() for a in agent.split(",") if a.strip()] if agent else None
    try:
        result = install_skill(
            resolved,
            name,
            force=force,
            install_dir=install_dir,
            agents=agents,
            scope=scope,
            project_root=project_root,
            recursive=not no_deps,
        )
    except LakeInsightError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(f"[green]已安装[/green] [cyan]{result['name']}[/cyan] v{result['version']}")
    for inst in result["installations"]:
        console.print(f"  → {inst.agent} [{inst.scope}]: {inst.path}")
    for v in result["verification"]:
        icon = "[green]✓[/green]" if v["discoverable"] else "[red]✗[/red]"
        console.print(f"  {icon} {v['agent']}: {v['detail']}")
    if result["dependencies"]:
        console.print(f"  依赖: {', '.join(result['dependencies'])}")


# ── skill remove ─────────────────────────────────────────────────────────────


@skill_app.command("remove")
def skill_remove(
    name: str,
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="只移除指定 agent 的安装副本"),
) -> None:
    """移除已安装的 skill（如被其他 skill 依赖会拒绝）。

    指定 --agent 时只移除该 agent 的安装，不影响其他 agent。
    """
    try:
        result = remove_skill(name, agent=agent)
    except LakeInsightError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(f"[green]已移除[/green] [cyan]{result['name']}[/cyan]")
    for p in result.get("removed") or []:
        console.print(f"  → {p}")


# ── skill update ─────────────────────────────────────────────────────────────


@skill_app.command("update")
def skill_update(
    ctx: typer.Context,
    name: str,
) -> None:
    """用源的最新版本刷新已安装的 skill（所有安装副本）。"""
    source = _get_source(ctx.obj.get("_source"))
    try:
        result = update_skill(source, name)
    except LakeInsightError as exc:
        console.print(f"[red]错误:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(f"[green]已更新[/green] [cyan]{result['name']}[/cyan]")
    for inst in result.get("installations") or []:
        console.print(f"  → {inst.agent} [{inst.scope}]: {inst.path}")


# ── skill agents ──────────────────────────────────────────────────────────────


@skill_app.command("agents")
def skill_agents() -> None:
    """探测本机已安装的 coding agents（按 skill 目录是否存在）。"""
    found = detect_agents()
    if not found:
        console.print("[yellow]未探测到任何 agent 的 skill 目录。[/yellow]")
        return
    console.print("检测到的 agents:")
    for a in found:
        console.print(f"  • [cyan]{a}[/cyan]")


# ── skill verify ──────────────────────────────────────────────────────────────


@skill_app.command("verify")
def skill_verify(name: str) -> None:
    """校验已安装 skill 是否可被 agent 发现。"""
    from .state import get_installed_skills
    from .verify import verify_all

    state = get_installed_skills().get(name)
    if state is None:
        console.print(f"[yellow]技能 {name} 未安装。[/yellow]")
        raise typer.Exit(code=1)

    records = [
        {"agent": i.agent, "skill": name, "path": i.path}
        for i in state.installations
    ]
    results = verify_all(records)
    for r in results:
        icon = "[green]✓[/green]" if r["discoverable"] else "[red]✗[/red]"
        console.print(f"  {icon} {r['agent']}: {r['detail']}")


# ── dev group callback ──────────────────────────────────────────────────────


@dev_app.callback(invoke_without_command=True)
def dev_main(
    ctx: typer.Context,
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Skill 源"),
) -> None:
    ctx.ensure_object(dict)
    if source is not None:
        ctx.obj["_source"] = source


# ── dev sync ─────────────────────────────────────────────────────────────────


@dev_app.command("sync")
def dev_sync() -> None:
    """将本地 skills/ 目录与 manifest.yaml 同步（开发者命令）。

    固定使用 LocalSource，与 config.yaml 的 default_source 无关。
    """
    from .config import REPO_ROOT
    from .source.local import LocalSource

    source = LocalSource()
    path = REPO_ROOT / "manifest.yaml"
    specs = sync_manifest(source, path)
    console.print(f"[green]已同步[/green] manifest.yaml，共 {len(specs)} 个 skill 条目。")


if __name__ == "__main__":
    app()
