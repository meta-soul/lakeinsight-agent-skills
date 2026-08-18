"""Typed exceptions for the lakeinsight CLI."""


class LakeInsightError(Exception):
    """Base exception for all lakeinsight errors."""

    exit_code: int = 1

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class SkillNotFoundError(LakeInsightError):
    def __init__(self, name: str) -> None:
        self.name = name
        msg = f"未找到技能 {name}，请确认该技能存在"
        super().__init__(msg)


class SkillAlreadyInstalledError(LakeInsightError):
    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version
        msg = f"技能 {name} 已安装（v{version}），需加 --force 重新安装"
        super().__init__(msg)


class SkillNotInstalledError(LakeInsightError):
    def __init__(self, name: str) -> None:
        self.name = name
        msg = f"技能 {name} 未安装，请先执行 install 命令"
        super().__init__(msg)


class InvalidManifestError(LakeInsightError):
    def __init__(self, path: str, detail: str = "") -> None:
        self.path = path
        msg = f"manifest 无效 ({path})" + (f": {detail}" if detail else "")
        super().__init__(msg)


class InvalidStateError(LakeInsightError):
    def __init__(self, detail: str = "") -> None:
        msg = f"状态文件无效" + (f": {detail}" if detail else "")
        super().__init__(msg)


class DownloadError(LakeInsightError):
    def __init__(self, name: str, detail: str = "") -> None:
        self.name = name
        msg = f"下载技能 {name} 失败" + (f": {detail}" if detail else "")
        super().__init__(msg)


class VersionNotFoundError(LakeInsightError):
    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version
        msg = f"技能 {name} 不存在版本 {version}"
        super().__init__(msg)


class DependencyResolutionError(LakeInsightError):
    def __init__(self, name: str, dep: str, detail: str = "") -> None:
        self.name = name
        self.dep = dep
        msg = f"无法解析依赖 {name} -> {dep}" + (f": {detail}" if detail else "")
        super().__init__(msg)


class DependentSkillExistsError(LakeInsightError):
    def __init__(self, name: str, dependents: list[str]) -> None:
        self.name = name
        self.dependents = dependents
        msg = f"无法移除 {name}：仍被以下技能依赖 — {', '.join(dependents)}"
        super().__init__(msg)


class UnknownAgentError(LakeInsightError):
    def __init__(self, agent: str, available: list[str]) -> None:
        self.agent = agent
        self.available = available
        msg = f"未知 agent '{agent}'，可用: {', '.join(available)}"
        super().__init__(msg)
