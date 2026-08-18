# lakeinsight CLI

管理 agent skills 的生命周期：列出、搜索、查看详情、安装、移除、更新。

## 安装

```bash
cd cli
pip install -e .
```

依赖：`typer`、`PyYAML`、`rich`（Python >= 3.10）。也可不安装，直接：

```bash
python -m lakeinsight skill list
```

## 命令

```
lakeinsight skill list                                     列出所有 skill 及其安装状态
lakeinsight skill info   <name>                            查看某个 skill 的详细元数据
lakeinsight skill search <keyword> [-v]                    按关键词搜索 skill
lakeinsight skill install <name[@version]> [--agent] [--all-agents] [--scope] [--force] [--no-deps]
                                                           安装 skill（及依赖）到指定 agent
lakeinsight skill remove  <name> [--agent]                 移除 skill（或单个 agent 的安装）
lakeinsight skill update  <name>                           从源拉取最新版本刷新所有安装
lakeinsight skill verify  <name>                           校验已安装 skill 是否可被 agent 发现
lakeinsight skill agents                                  探测本机已安装的 coding agents
lakeinsight dev sync                                      将本地 skills/ 同步到 manifest.yaml
lakeinsight --version                                      显示版本
lakeinsight --verbose / --debug                            启用详细 / 调试日志
```

### 示例

```bash
# 列出可用技能
lakeinsight skill list

# 查看详情
lakeinsight skill info bi-task

# 搜索
lakeinsight skill search dashboard

# 安装到单个 agent（默认 global scope）
lakeinsight skill install bi-task --agent opencode

# 安装到多个 agent（逗号分隔）
lakeinsight skill install bi-task --agent opencode,claude-code

# 安装到所有已探测的 agent
lakeinsight skill install bi-task --all-agents

# 安装到 project scope（项目根自动检测 .git）
lakeinsight skill install bi-task --agent opencode --scope project

# 指定 project root
lakeinsight skill install bi-task --agent opencode --scope project --project-root ~/my-repo

# 安装指定版本 + 跳过自动安装依赖
lakeinsight skill install bi-task@1.2.0 --agent opencode --no-deps

# 已安装时强制重装
lakeinsight skill install bi-task --agent opencode --force

# 更新（从源拉取最新）
lakeinsight skill update bi-task

# 移除单个 agent 的安装副本（不影响其他 agent）
lakeinsight skill remove bi-task --agent opencode

# 移除全部安装副本
lakeinsight skill remove bi-task

# 探测本机 agent
lakeinsight skill agents

# 校验可发现性
lakeinsight skill verify bi-task
```

## 安装目标：agent / scope

安装到哪个目录由 **agent + scope** 决定，默认 `scope=global`：

| agent | global 目录 | project 目录 | 方式 |
|-------|-------------|--------------|------|
| opencode | `~/.config/opencode/skills/` | `<root>/.opencode/skills/` | copy |
| claude-code | `~/.claude/skills/` | `<root>/.claude/skills/` | copy |
| copilot | `~/.copilot/skills/` | `<root>/.github/skills/` | copy |
| codex | `~/.codex/skills` → `~/.agents/skills`（候选探测，existing > default） | `<root>/.codex/skills/` | copy |
| cursor | `~/.cursor/rules/` | `<root>/.cursor/rules/` | **转换** `.mdc` rule |
| custom | `--install-dir <path>` | — | copy |

- 不指定 `--agent` 时**报错**（绝不自动安装到全部 agent），需显式指定或 `--install-dir`。
- project scope 的根目录优先级：`--project-root` > 向上找 `.git` > 当前目录。
- Cursor 不是 copy，而是把 `SKILL.md` 转换成 `.cursor/rules/<name>.mdc`，其中 `globs` / `alwaysApply` 由 SKILL.md 的 `agent.cursor` 元数据控制。

## Agent 专属元数据

`SKILL.md` frontmatter 可加 `agent:` 段，控制各 agent 的差异（Cursor 使用）：

```yaml
---
name: lakehouse-sql
description: ...
agent:
  cursor:
    globs:
      - "**/*.sql"
    alwaysApply: false
---
```

## Skill Source 抽象

CLI 通过 `SkillSource` 协议与 skill 提供方解耦。**默认 source 固定为官方 skill 仓库**，用户无需每次指定：

- **GitHubSource**（默认）—— 官方 skill 仓库（地址在 `config.py` 的 `DEFAULT_GITHUB_*` 常量）

### 默认仓库与覆盖

```bash
# 直接用默认官方仓库
lakeinsight skill list
lakeinsight skill install bi-task --agent opencode

# 覆盖：命令行临时指定其他仓库
lakeinsight --source github:owner/repo skill list

# 覆盖：config.yaml 永久指定
#   default_source: github
#   github:
#     owner: xxx
#     repo: xxx
#     ref: main
```

优先级：`--source` 参数 > `~/.lakeinsight/config.yaml` > 代码内置默认（官方仓库）。未知 source 直接报错，不回退。

- 通过 **SSH `git clone --depth 1`** 拉取（`git@github.com:owner/repo.git`），支持私有仓库，自动用本机 SSH key / git 凭据，**无需 token**
- clone 缓存到 `~/.lakeinsight/cache/github/<owner>/<repo>/clones/`
- **缓存按 commit SHA 校验**：每次拉取前用 `git ls-remote` 对比远程最新 SHA，远程更新后自动重新 clone；网络不可达时降级用本地缓存
- tags 用 `git ls-remote --tags` 获取，结果缓存 1 小时
- `list` / `info` 读 clone 里的 `manifest.yaml`，没有则回退扫描 `skills/` 目录
- `install` 解析版本优先用 `manifest.yaml`（最新版本）+ git tags（历史版本），两者都没有时才读 clone 目录兜底

## 架构：manifest 与 state 分离

| 文件 | 内容 | 谁写 |
|------|------|------|
| `manifest.yaml`（仓库根） | skill 注册表：名称、版本、描述、关键词、MCP 依赖、skill 间依赖 | `sync` 命令（CLI 从 source 读取并写入） |
| `~/.lakeinsight/state.yaml` | 安装状态：版本、installations（agent/scope/root/path）、安装时间、已解析依赖 | `install` / `remove` / `update` |

manifest.yaml 中**不含**安装状态字段（如 `installed` / `install_path`），避免仓库文件被用户本地状态污染。

manifest.yaml 是**只读注册表**：GitHubSource 用远程 manifest.yaml 做快速索引；`dev sync` 用内部目录读取器（LocalSource）扫本地 `skills/` 生成它（`lakeinsight dev sync`）。

每个 skill 可装到多个 agent/scope，state 里是 `installations` 列表（每个有稳定的 `id = sha256(agent+scope+root+skill)[:8]`），`remove --agent` 只删对应条目。

## 版本与依赖

- 安装支持版本约束：`bi-task@1.2.0`、`bi-task@>=1.0`、`bi-task@^1.0`、`bi-task@*`
- SKILL.md frontmatter 中可声明 `dependencies: { lake-query: ">=1.0" }`，安装时自动递归安装
- 默认递归安装依赖（`--no-deps` 可跳过）
