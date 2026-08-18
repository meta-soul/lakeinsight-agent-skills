---
name: bi-task
version: 1.0.0
keywords:
  - 数据看板
  - 数据报表
  - 数据大屏
  - 可视化
  - 图表
  - dashboard
  - BI
  - 面板
description: 生成数据看板、数据报表、数据大屏、可视化图表、BI面板时使用。
  当用户需要查询数据并生成可视化图表或数据看板时触发。关键字可以是数据看板, 数据报表, 数据大屏,
  可视化, 图表, dashboard, BI, 面板, 数据面板,数据报表，可视化报表，可视化面板，数据看板，bi看板， 生成报表, 看板文件, 数据展示, lakesoul，BI报表
mcp_required:
  - lakeinsight-mcp
---

# BI 数据看板生成技能

## 核心原则

先通过 MCP 数据源工具查数据，查到再生成代码；查不到直接退出，不生成模板。
**生成代码后默认调用 bi_task_publish 发布任务。**

## 执行流程

1. 确认用户 Schema 和分析需求
2. 使用 Lakesoul MCP 查询 Schema / Table / Field
3. 分析字段特征决定页面和图表
4. 调用 bi_task_get_full_app 获取完整应用模板（内部自动调 `/user/getPrestoInfo` 获取有效 Token，注入模板）
5. 追加分析页面（禁止覆盖 pages），**严禁裁剪/删除/简化模板的任何基础设施代码**（详见 `references/constraints.md` 第 17 条）
6. 写入 .py 文件（暗色主题已内置，自定义主题通过 theme_config 参数传入）
7. **调用 bi_task_publish 发布任务**

## 关键 MCP 工具

| 工具名                  | 用途                                                                                                             | 何时调用             |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------- | -------------------- |
| bi_task_get_full_app    | 获取完整 Python 应用模板（含概览页、导航等，自动获取 Token）                                                     | 确认数据存在后       |
| bi_task_get_component   | 获取 KPI 卡片等独立组件的 CSS/JS/Python 代码                                                                     | 需要组件代码时       |
| bi_task_list_components | 列出所有可用组件                                                                                                 | 不确定有哪些组件时   |
| **bi_task_publish**     | 发布 .py 文件为 BI 任务。参数：file_path（必填）、description（可选）、theme_config（可选）。自动分片上传 + 启动 | 文件写入后默认调用   |
| bi_task_start           | 手动启动已发布的任务                                                                                             | 发布后自动启动失败时 |

## 详细规则

- MCP 工具规范与执行流程 → references/workflow.md
- Streamlit 组件规范 → references/streamlit.md
- Plotly 图表规范 → references/plotly.md
- 异常和禁止事项 → references/constraints.md
