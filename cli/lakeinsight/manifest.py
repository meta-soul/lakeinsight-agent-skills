"""Load and save the skills manifest (manifest.yaml).

The manifest is the **skill registry** — it only contains skill definitions,
never install state.  State lives in ~/.lakeinsight/state.yaml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config import MANIFEST_VERSION
from .errors import InvalidManifestError
from .spec import SkillSpec


def default_manifest() -> dict[str, Any]:
    return {
        "manifest_version": MANIFEST_VERSION,
        "skills": {},
    }


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_manifest()
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise InvalidManifestError(str(path), "内容不是 YAML 对象")
    data.setdefault("manifest_version", MANIFEST_VERSION)
    data.setdefault("skills", {})
    if not isinstance(data["skills"], dict):
        raise InvalidManifestError(str(path), "skills 必须是 YAML 映射")
    return data


def load_skill_specs(manifest_path: Path) -> dict[str, SkillSpec]:
    """Load manifest and return a dict of {name: SkillSpec}."""
    data = load_manifest(manifest_path)
    specs: dict[str, SkillSpec] = {}
    raw_skills: dict[str, Any] = data.get("skills", {})
    for name, entry in raw_skills.items():
        if not isinstance(entry, dict):
            continue
        specs[name] = SkillSpec.from_dict(name, entry)
    return specs


def save_manifest(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)


def write_skill_specs(specs: dict[str, SkillSpec], path: Path) -> None:
    data = default_manifest()
    for name, spec in specs.items():
        data["skills"][name] = spec.to_dict()
    save_manifest(data, path)
