"""Skill lifecycle operations: list / install / remove / update / info / search.

These are pure functions that compose ``SkillSource`` + state + filesystem.
They do NOT import typer / rich — presentation is in cli.py.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from . import logger
from .agents import DetectAdapter, get_adapter
from .config import CACHE_DIR, get_install_dir, get_project_root
from .errors import (
    DependentSkillExistsError,
    DownloadError,
    SkillAlreadyInstalledError,
    SkillNotFoundError,
    SkillNotInstalledError,
)
from .source import SkillSource
from .spec import SkillSpec, Version, parse_install_spec
from .state import (
    Installation,
    InstalledSkill,
    get_installed_skills,
    is_installed,
    make_installation_id,
    remove_installation,
    remove_installed_skill,
    set_installed_skill,
    timestamp,
)
from .verify import verify_agent_skill

LOG = logger.LOG


# ── helpers ──────────────────────────────────────────────────────────────────


def _resolve_spec_version(
    source: SkillSource, name: str, constraint: str
) -> tuple[SkillSpec, Version]:
    spec = source.get_skill(name)
    if spec is None:
        raise SkillNotFoundError(name)
    version = source.resolve_version(name, constraint)
    if version is None:
        raise SkillNotFoundError(name)
    return spec, version


def _resolve_targets(
    agents: list[str] | None,
    scope: str,
    project_root: Path | None,
    install_dir: Path | None,
) -> list[dict[str, Any]]:
    """Resolve install targets from (agents, scope, root) or a custom dir.

    Each target dict carries ``agent``, ``scope``, ``root``, ``dir``, ``adapter``
    and ``resolver``.  ``adapter`` is None for custom (plain copy) installs.
    """
    if install_dir is not None:
        d = Path(install_dir).expanduser()
        return [{
            "agent": "custom",
            "scope": "custom",
            "root": "",
            "dir": d,
            "adapter": None,
            "resolver": "",
        }]

    if not agents:
        raise ValueError("请指定 --agent（如 opencode,claude-code）或 --install-dir")

    root = ""
    root_path: Path | None = None
    if scope == "project":
        root_path = get_project_root(explicit=project_root)
        root = str(root_path)

    targets: list[dict[str, Any]] = []
    for a in agents:
        adapter = get_adapter(a)
        if isinstance(adapter, DetectAdapter):
            if scope == "project":
                d = adapter.resolve_project_dir(root_path)  # type: ignore[arg-type]
                resolver = ""
            else:
                d, resolver = adapter.detected_global_dir()
        else:
            d = adapter.resolve_dir(scope, root_path)
            resolver = ""
        targets.append({
            "agent": a,
            "scope": scope,
            "root": root,
            "dir": d,
            "adapter": adapter,
            "resolver": resolver,
        })
    return targets


def _copy_to(skill_dir: Path, target_dir: Path, skill_name: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / skill_name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(skill_dir, target)
    return target


def _install_tree(
    source: SkillSource,
    spec: SkillSpec,
    version: Version,
    targets: list[dict[str, Any]],
    visited: set[str],
    force: bool,
    recursive: bool = True,
) -> InstalledSkill:
    """Install a skill *and* its dependencies recursively (topological pre-order)."""
    if spec.name in visited:
        return get_installed_skills().get(spec.name, InstalledSkill(spec.name, version))
    visited.add(spec.name)

    dep_names: list[str] = []
    if recursive:
        for dep_name, dep_constraint in spec.dependencies.items():
            dep_spec, dep_version = _resolve_spec_version(source, dep_name, dep_constraint)
            _install_tree(source, dep_spec, dep_version, targets, visited, force, recursive)
            dep_names.append(dep_name)

    cache = CACHE_DIR / spec.name / str(version)
    try:
        source.download(spec.name, version, cache)
    except Exception as exc:
        raise DownloadError(spec.name, str(exc)) from exc

    existing = get_installed_skills().get(spec.name)
    existing_by_id = {i.id: i for i in (existing.installations if existing else [])}

    new_installs: list[Installation] = []
    for t in targets:
        inst_id = make_installation_id(t["agent"], t["scope"], t["root"], spec.name)
        if inst_id in existing_by_id and not force:
            LOG.info("目标已安装，跳过 %s@%s → %s", spec.name, version, t["dir"])
            continue
        adapter = t["adapter"]
        if adapter is None:
            artifact = _copy_to(cache, t["dir"], spec.name)
        else:
            artifact = adapter.install(cache, t["dir"], spec.name, spec)
        LOG.info("安装 %s@%s (%s/%s) → %s", spec.name, version, t["agent"], t["scope"], artifact)
        new_installs.append(
            Installation(
                id=inst_id,
                agent=t["agent"],
                scope=t["scope"],
                path=str(artifact),
                root=t["root"],
                slug=_slug(t["root"]),
                resolver=t["resolver"],
            )
        )

    final_installs = list(existing.installations) if existing else []
    for ni in new_installs:
        final_installs = [i for i in final_installs if i.id != ni.id]
        final_installs.append(ni)

    entry = InstalledSkill(
        name=spec.name,
        version=version,
        installed_at=timestamp(),
        dependencies=dep_names,
        installations=final_installs,
    )
    set_installed_skill(entry)
    return entry


def _slug(root: str) -> str:
    return Path(root).name if root else ""


# ── public API ───────────────────────────────────────────────────────────────


def list_skills(source: SkillSource) -> list[dict[str, Any]]:
    """Return all available skills with their install status cross-referenced."""
    specs = source.list_skills()
    installed = get_installed_skills()
    result: list[dict[str, Any]] = []
    for name, spec in sorted(specs.items()):
        state = installed.get(name)
        result.append({
            "spec": spec,
            "installed": state is not None,
            "installed_version": str(state.version) if state else None,
            "installations": state.installations if state else [],
        })
    return result


def get_skill_info(source: SkillSource, name: str) -> dict[str, Any]:
    """Detailed info for a single skill."""
    spec = source.get_skill(name)
    if spec is None:
        raise SkillNotFoundError(name)
    state = get_installed_skills().get(name)
    versions = source.list_versions(name)
    return {
        "spec": spec,
        "installed": state is not None,
        "installed_version": str(state.version) if state else None,
        "installed_at": state.installed_at if state else None,
        "available_versions": [str(v) for v in versions],
        "dependencies_installed": state.dependencies if state else [],
        "installations": state.installations if state else [],
    }


def install_skill(
    source: SkillSource,
    raw_spec: str,
    *,
    force: bool = False,
    install_dir: Path | None = None,
    agents: list[str] | None = None,
    scope: str = "global",
    project_root: Path | None = None,
    recursive: bool = True,
) -> dict[str, Any]:
    """Install a skill (and optionally its dependencies) to the resolved targets."""
    name, constraint = parse_install_spec(raw_spec)
    spec, version = _resolve_spec_version(source, name, constraint)

    try:
        targets = _resolve_targets(agents, scope, project_root, install_dir)
    except ValueError as exc:
        raise SkillNotFoundError(str(exc)) from exc

    # Top-level conflict check (deps are handled inside _install_tree).
    existing = get_installed_skills().get(spec.name)
    if existing and not force:
        existing_ids = {i.id for i in existing.installations}
        for t in targets:
            if make_installation_id(t["agent"], t["scope"], t["root"], spec.name) in existing_ids:
                raise SkillAlreadyInstalledError(spec.name, str(existing.version))

    if recursive:
        entry = _install_tree(source, spec, version, targets, set(), force, recursive=True)
    else:
        entry = _install_tree(source, spec, version, targets, set(), force, recursive=False)

    verifications = [
        verify_agent_skill(t["agent"], spec.name, t["dir"], spec) for t in targets
    ]

    target_ids = {
        make_installation_id(t["agent"], t["scope"], t["root"], spec.name)
        for t in targets
    }
    return {
        "name": spec.name,
        "version": str(version),
        "installations": [i for i in entry.installations if i.id in target_ids],
        "verification": verifications,
        "dependencies": entry.dependencies,
    }


def remove_skill(name: str, agent: str | None = None) -> dict[str, Any]:
    """Remove an installed skill, or a single agent's installation of it.

    Refuses to remove the whole skill if another installed skill depends on it.
    """
    if not is_installed(name):
        raise SkillNotInstalledError(name)

    state = get_installed_skills()[name]

    if agent is not None:
        matches = [i for i in state.installations if i.agent == agent]
        if not matches:
            raise SkillNotInstalledError(f"{name} (agent={agent})")
        removed: list[Path] = []
        for inst in matches:
            remove_installation(name, inst.id)
            p = Path(inst.path)
            if p.exists():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            removed.append(p)
        LOG.info("已移除 %s 的 %s 安装副本", name, agent)
        return {"name": name, "agent": agent, "removed": [str(p) for p in removed]}

    dependents = _find_dependents(name)
    if dependents:
        raise DependentSkillExistsError(name, dependents)

    removed: list[Path] = []
    for inst in state.installations:
        p = Path(inst.path)
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        removed.append(p)
    remove_installed_skill(name)
    LOG.info("已移除 %s", name)
    return {"name": name, "removed": [str(p) for p in removed]}


def _find_dependents(name: str) -> list[str]:
    """Return skills that declare a dependency on ``name``."""
    deps: list[str] = []
    for n, installed in get_installed_skills().items():
        if name in installed.dependencies:
            deps.append(n)
    return sorted(deps)


def update_skill(source: SkillSource, name: str) -> dict[str, Any]:
    """Re-install the latest version to every existing installation.

    Each installation is rebuilt from its own (agent, scope, root), so multiple
    project installs of the same agent keep their distinct roots.
    """
    if not is_installed(name):
        raise SkillNotInstalledError(name)
    state = get_installed_skills()[name]

    result: dict[str, Any] = {"name": name, "installations": []}
    for inst in state.installations:
        if inst.agent == "custom":
            r = install_skill(
                source, name, force=True,
                install_dir=Path(inst.path).parent,
            )
        else:
            root = Path(inst.root) if inst.root else None
            r = install_skill(
                source, name, force=True,
                agents=[inst.agent], scope=inst.scope, project_root=root,
            )
        result["installations"].extend(r["installations"])
        result["version"] = r["version"]
    return result


def search_skills(source: SkillSource, query: str) -> list[SkillSpec]:
    """Simple keyword search across skill names, descriptions, and keywords."""
    specs = source.list_skills()
    q = query.lower()
    results: list[tuple[int, SkillSpec]] = []
    for name, spec in specs.items():
        score = 0
        if q in name.lower():
            score += 100
        if q in spec.description.lower():
            score += 50
        for kw in spec.keywords:
            if q in str(kw).lower():
                score += 30
        if score > 0:
            results.append((score, spec))
    results.sort(key=lambda x: x[0], reverse=True)
    return [spec for _, spec in results]


def sync_manifest(source: SkillSource, manifest_path: Path) -> dict[str, SkillSpec]:
    """Sync the local manifest.yaml from a source."""
    return source.sync_manifest(manifest_path)
