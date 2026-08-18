"""GitHubSource — fetch skills from a GitHub repository via SSH ``git clone``.

Version management supports **both** layouts:

- **Directory layout** (same as :class:`LocalSource`): ``skills/<name>/<version>/SKILL.md``
  on the default branch — versions are discovered from the directory names.
- **Git tags**: the default branch holds the latest ``skills/<name>/SKILL.md`` and each
  release tag (e.g. ``v1.2.0``) snapshots a version — versions come from the repo's tags.

``download`` prefers the directory layout, then falls back to the matching tag.

Uses ``git clone --depth 1`` over SSH (``git@github.com:owner/repo.git``), so it
works with private repositories via the user's local SSH key / git credentials —
no token needed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .. import logger
from ..config import CACHE_DIR
from ..errors import DownloadError, SkillNotFoundError
from ..spec import SkillSpec, Version

from . import SkillSource
from .local import LocalSource

LOG = logger.LOG

_TAG_LINE_RE = re.compile(r"refs/tags/(.+)$")
_TAGS_TTL = 3600  # cache git tags for 1 hour


def _parse_tag_version(tag: str) -> Version | None:
    """Parse a git tag like ``v1.2.0`` / ``1.2.0`` into a Version (or None)."""
    t = tag.strip()
    if t.startswith("v") or t.startswith("V"):
        t = t[1:]
    v = Version.parse(t)
    if v == Version(0, 0, 0):
        return None
    return v


def _parse_manifest_yaml(raw: str) -> dict[str, SkillSpec]:
    """Parse a manifest.yaml body into {name: SkillSpec}.  Empty on any error."""
    try:
        import yaml

        data = yaml.safe_load(raw) or {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    skills = data.get("skills", {})
    if not isinstance(skills, dict):
        return {}
    specs: dict[str, SkillSpec] = {}
    for name, entry in skills.items():
        if isinstance(entry, dict):
            specs[str(name)] = SkillSpec.from_dict(str(name), entry)
    return specs


class GitHubSource(SkillSource):
    name = "github"

    def __init__(self, owner: str, repo: str, ref: str = "main") -> None:
        self.owner = owner
        self.repo = repo
        self.ref = ref
        self._cache_root = CACHE_DIR / "github" / self.owner / self.repo

    # ── git helpers ───────────────────────────────────────────────────────────

    def _git_url(self) -> str:
        return f"git@github.com:{self.owner}/{self.repo}.git"

    def _git_clone(self, ref: str, dest: Path) -> None:
        """Shallow-clone ``ref`` (branch or tag) into ``dest`` via SSH."""
        url = self._git_url()
        out = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", ref, url, str(dest)],
            capture_output=True, text=True, timeout=180,
        )
        if out.returncode != 0:
            raise DownloadError(
                f"{self.owner}/{self.repo}",
                f"git clone 失败: {(out.stderr or out.stdout).strip()}",
            )

    def _remote_sha(self, ref: str, kind: str) -> str:
        """Return the remote commit SHA for a ref (empty string if unreachable)."""
        url = self._git_url()
        remote_ref = f"refs/{kind}/{ref}"
        try:
            out = subprocess.run(
                ["git", "ls-remote", url, remote_ref],
                capture_output=True, text=True, timeout=30,
            )
            if out.returncode == 0:
                for line in out.stdout.splitlines():
                    if remote_ref in line:
                        sha = line.split("\t")[0].strip()
                        if sha:
                            return sha
        except Exception:
            pass
        return ""

    @staticmethod
    def _cache_valid(clone_dir: Path, sha_file: Path, remote_sha: str) -> bool:
        """Whether the cached clone is still fresh.

        - No cached clone → invalid.
        - Remote SHA unreachable → keep cache (graceful degradation).
        - Remote SHA differs from recorded one → invalid (re-clone).
        """
        if not clone_dir.exists():
            return False
        if not remote_sha:
            return True
        if not sha_file.exists():
            return False
        return sha_file.read_text(encoding="utf-8").strip() == remote_sha

    def _fetch(self, ref: str, kind: str) -> Path:
        """Clone a branch/tag snapshot; return the clone directory.

        The clone is cached locally.  On re-fetch we compare the remote commit
        SHA against the cached one and re-clone only when it changed.
        """
        safe = ref.replace("/", "-")
        clone_dir = self._cache_root / "clones" / kind / safe
        sha_file = self._cache_root / "clones" / f"{kind}-{safe}.sha"

        remote_sha = self._remote_sha(ref, kind)
        if self._cache_valid(clone_dir, sha_file, remote_sha):
            return clone_dir

        if clone_dir.exists():
            shutil.rmtree(clone_dir)
        self._git_clone(ref, clone_dir)
        if remote_sha:
            sha_file.parent.mkdir(parents=True, exist_ok=True)
            sha_file.write_text(remote_sha, encoding="utf-8")
        return clone_dir

    def _skills_dir(self, ref: str, kind: str) -> Path:
        return self._fetch(ref, kind) / "skills"

    def _local_for(self, ref: str, kind: str) -> LocalSource:
        return LocalSource(root=self._skills_dir(ref, kind))

    def _fetch_tags(self) -> list[str]:
        """Return git tags via ``git ls-remote``, caching the result."""
        cache = self._cache_root / "tags.json"
        if cache.exists() and time.time() - cache.stat().st_mtime < _TAGS_TTL:
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                tags = data.get("tags")
                if isinstance(tags, list):
                    return [str(t) for t in tags]
            except Exception:
                pass

        tags = self._ls_remote_tags()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"tags": tags}), encoding="utf-8")
        return tags

    def _ls_remote_tags(self) -> list[str]:
        url = self._git_url()
        try:
            out = subprocess.run(
                ["git", "ls-remote", "--tags", url],
                capture_output=True, text=True, timeout=30,
            )
        except Exception:
            return []
        if out.returncode != 0:
            return []
        tags: list[str] = []
        for line in out.stdout.splitlines():
            m = _TAG_LINE_RE.search(line)
            if not m:
                continue
            name = m.group(1)
            if name.endswith("^{}"):
                name = name[:-3]
            if name and name not in tags:
                tags.append(name)
        return tags

    def _tag_for_version(self, version: Version) -> str | None:
        target = str(version)
        for tag in self._fetch_tags():
            v = _parse_tag_version(tag)
            if v is not None and str(v) == target:
                return tag
        return None

    # ── SkillSource interface ────────────────────────────────────────────────

    def _fetch_manifest_specs(self) -> dict[str, SkillSpec]:
        """Read manifest.yaml from the cached clone ({} on any failure)."""
        root = self._fetch(self.ref, "heads")
        manifest = root / "manifest.yaml"
        if manifest.exists():
            return _parse_manifest_yaml(manifest.read_text(encoding="utf-8"))
        return {}

    def list_skills(self) -> dict[str, SkillSpec]:
        specs = self._fetch_manifest_specs()
        if specs:
            return specs
        return self._local_for(self.ref, "heads").list_skills()

    def get_skill(self, name: str) -> SkillSpec | None:
        specs = self._fetch_manifest_specs()
        if specs:
            return specs.get(name)
        return self._local_for(self.ref, "heads").get_skill(name)

    def list_versions(self, name: str) -> list[Version]:
        versions: dict[str, Version] = {}

        # 1. manifest.yaml（最新版本）
        specs = self._fetch_manifest_specs()
        if name in specs:
            v = specs[name].version
            if v != Version(0, 0, 0):
                versions[str(v)] = v

        # 2. git tags（历史版本）
        for tag in self._fetch_tags():
            v = _parse_tag_version(tag)
            if v is not None:
                versions.setdefault(str(v), v)

        # 3. 兜底：manifest 与 tags 都没有版本时，才读 clone 目录的版本目录
        if not versions:
            try:
                for v in self._local_for(self.ref, "heads").list_versions(name):
                    if v != Version(0, 0, 0):
                        versions[str(v)] = v
            except (SkillNotFoundError, DownloadError):
                pass

        return sorted(versions.values())

    def download(self, name: str, version: Version, target: Path) -> Path:
        # 1. directory layout on the default branch
        try:
            return self._local_for(self.ref, "heads").download(name, version, target)
        except (SkillNotFoundError, DownloadError):
            pass

        # 2. matching git tag
        tag = self._tag_for_version(version)
        if tag:
            skill_dir = self._skills_dir(tag, "tags") / name
            if skill_dir.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(skill_dir, target)
                LOG.debug("copied tag %s → %s", tag, target)
                return target

        raise SkillNotFoundError(name)
