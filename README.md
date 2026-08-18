# lakeinsight-agent-skills

LakeInsight Agent Skills — 面向 LakeInsight / LakeSoul 数据平台的 agent 技能仓库。

## 项目结构

```
.
├── cli/                # lakeinsight CLI：管理 skill 生命周期
│   ├── lakeinsight/    #    Python 包
│   │   ├── cli.py      #    typer 入口
│   │   ├── config.py   #    路径 & 常量（含 project root 解析）
│   │   ├── errors.py   #    类型化异常
│   │   ├── logger.py   #    日志系统
│   │   ├── manifest.py #    manifest.yaml 读写（仅 skill 定义，无安装状态）
│   │   ├── agents.py   #    AgentAdapter 抽象（copy / detect / rule 转换）+ 注册表
│   │   ├── verify.py   #    安装后可发现性校验
│   │   ├── spec.py     #    SkillSpec / Version / VersionRange（含 agent 元数据）
│   │   ├── state.py    #    ~/.lakeinsight/state.yaml（installations 独立存储）
│   │   ├── skill.py    #    skill 核心竞争力（install / remove / update / info / search）
│   │   └── source/     #    SkillSource 抽象层（github + local 内部读取）
│   ├── pyproject.toml
│   └── README.md
├── skills/             # agent 技能本体（AI 能力，每个含 SKILL.md + references/）
│   ├── bi-task/        #    BI 数据看板生成技能
│   ├── create-task/    #    数据开发任务创建技能
│   ├── jar-task/       #    JAR 程序包任务技能
│   └── upload-package/ #    程序包上传技能
├── manifest.yaml       # skill 注册表（纯元数据，无安装状态）
└── README.md
```

## 快速开始

```bash
# 安装 CLI
cd cli
pip install -e .

# 列出技能
lakeinsight skill list

# 搜索
lakeinsight skill search dashboard

# 查看详情
lakeinsight skill info bi-task

# 安装到指定 agent（默认 global scope）
lakeinsight skill install bi-task --agent opencode

# 安装到多个 agent + project scope
lakeinsight skill install bi-task --agent opencode,claude-code --scope project

# 指定版本
lakeinsight skill install bi-task@1.2.0 --agent opencode

# 更新 / 移除（可只移除单个 agent）
lakeinsight skill update bi-task
lakeinsight skill remove bi-task --agent opencode

# 校验可发现性
lakeinsight skill verify bi-task
```

详细用法见 [cli/README.md](cli/README.md)。

## 技能规范

每个技能是 `skills/<name>/` 目录，核心是 `SKILL.md`：

```markdown
---
description: 什么时候使用、触发关键字
version: 1.0.0
keywords: [看板, 报表]
mcp_required:
  - lakeinsight-mcp-server
dependencies:
  lake-query: ">=1.0"
---

# 技能名称

## 何时使用
...

## 输入
...

## 工作流程
...

## 输出规范
...
```

约定：

- `SKILL.md` 的 YAML frontmatter 描述触发条件、版本、依赖的 MCP server、skill 间依赖
- 可用 `agent:` 段控制各 agent 差异（Cursor 转换 `.mdc` 时读取）：
  ```yaml
  agent:
    cursor:
      globs: ["**/*.sql"]
      alwaysApply: false
  ```
- 附属规范放 `references/`，脚本放 `scripts/`
- 技能应遵循「先查数据、确认存在、再生成」的原则，禁止无数据生成

## 架构原则

| 关注点 | 实现 |
|--------|------|
| **解耦 source** | `SkillSource` 协议：GitHubSource（默认官方仓库）/ LocalSource（内部目录读取） |
| **manifest / state 分离** | `manifest.yaml` = 只读注册表；`~/.lakeinsight/state.yaml` = 安装状态（installations 列表） |
| **Agent 适配** | `AgentAdapter` 协议：copy / detect / rule 转换三种方式，agent 路径差异收敛于此 |
| **可发现性校验** | `verify.py`：安装后校验「文件存在 ≠ agent 能发现」 |
| **版本语义** | `install <name>@>=1.0` / `@^1.2` / `@~1.2.3` 支持 npm 风格约束 |
| **依赖管理** | SKILL.md 中 `dependencies` 声明，安装时自动递归解析安装 |
| **日志分级** | `--verbose` / `--debug` 控制日志量 |

## 现有技能

| 技能 | 版本 | 用途 |
| ---- | ---- | ---- |
| `bi-task` | 1.0.0 | 生成数据看板 / 报表 / 大屏 / 可视化图表（BI 面板） |
| `create-task` | 1.0.0 | 创建 / 更新 LakeInsight 数据开发任务（Flink / Spark / Python） |
| `jar-task` | 1.0.0 | 创建 Flink / Spark 程序包任务（JAR 任务） |
| `upload-package` | 1.0.0 | 上传程序包文件到 LakeInsight 平台 |
