---
name: create-task
version: 1.0.0
keywords:
  - Flink
  - Spark
  - Python
  - Ray
  - RayJob
  - 任务
  - submit_approval
  - dataDev
  - 流任务
  - 批任务
  - sql_engine
mcp_required:
  - lakeinsight-mcp
dependencies:
  ray-job: ">=1.0.0"
description: |
  创建或更新 LakeInsight 数据开发任务，支持 Flink、Spark、Python 和 Ray 四种引擎。
  覆盖任务创建、配置更新、版本管理全流程。
  当用户说"创建任务"、"新建 Flink 任务"、"写个 Spark 批处理"、"跑 Python 脚本"、"创建 RayJob"、
  "更新任务"、"修改任务配置"、"发布新版本"时触发。
  Keywords: Flink, Spark, Python, Ray, RayJob, 任务, submit_approval, dataDev, 流任务, 批任务, sql_engine
---

# LakeInsight 数据开发任务

LakeSoul Daft 读写规则读取 `daft-lakesoul` skill。创建或配置 `sql_engine: 3` 的 RayJob 时必须读取 `ray-job` skill。

## 引擎选择

根据用户需求选择引擎，对应 `sql_engine` 值：

| 场景                                   | 引擎   | sql_engine | 允许的 job_type            |
| :------------------------------------- | :----- | :--------- | :------------------------- |
| 实时流处理、CDC 同步、低延迟计算       | Flink  | 0          | `stream` 或 `batch`        |
| 离线批量计算、数仓 ETL、大规模数据处理 | Spark  | 1          | 固定为 `batch`（不支持流） |
| 自定义 Python 脚本、机器学习、数据处理 | Python | 2          | 固定为 `batch`（不支持流） |
| Ray/Daft 分布式 Python 批处理          | Ray    | 3          | 固定为 `batch`（不支持流） |

> **提示**：用户没有明确说明时，默认推荐 Flink（流处理场景更通用）。

---

## 核心参数规范

## 脚本内容读取与填充规范（核心流程）

在新建或更新涉及到路径变更的任务时，`sql_details` 字段**绝不能**直接留空。大模型必须遵循以下严密的执行链条：

### 1. 强制前置动作：先读取，再组装

当用户提供了 `node_path`（如 `/spark/etl.sql` 或 `/jobs/sync.py`）时，大模型**不允许直接调用 `submit_approval`**。

- **第一步**：必须先使用相关的系统文件读取工具，把该路径下的脚本/代码文本**完整读取出来**。
- **第二步**：将读取到的源码文本，原封不动地填充到 JSON 报文的 `sql_details` 字段中。

### 2. 不同文件类型的填充细节

- **标准 SQL 脚本 (`.sql`) 与 Python 脚本 (`.py`)**：直接读取全部文本，完整塞进 `sql_details`。
- **Jupyter Notebook 文件 (`.ipynb`)**：
  - 大模型只需像对待普通文件一样读取其 JSON 文本或指定路径。
  - **特殊底座兜底**：若底层系统支持自动解析，可直接透传路径；若系统要求前端显式提交，大模型需过滤提取出所有 `code` 类型的 cells 文本，拼接后填入 `sql_details`。

### 3. 错误处理与用户提示

- 如果在执行前置动作时，发现 `node_path` 对应的文件不存在、无权限读取或内容为空：
  - **立即中断流程**，向用户明确报错（例如：“未找到指定的脚本文件，请确认路径是否正确”），**禁止**带着空的 `sql_details` 强行提交任务。

---

### 自定义参数 (`params`)

当用户需要透传自定义配置或运行参数时，使用 `params` 字段。

- **格式要求**：`--key value`，多个配置项之间用**空格**分隔。
- **示例**：`--nummarkEnd 40000 --nummarkLimit 36000`

---

## ⚠️ 任务名与路径清洗规则（必读）

底层 Skill 系统对 `name`（任务名）和 `node_path`（脚本路径）有一套自动清洗和兜底机制。在组装参数时请务必遵循以下行为：

### 1. 自动转换与清洗规范（对齐 K8s 命名限制）

底层系统在接收到 `name` 后，会自动执行以下清洗动作。大模型在理解用户意图时需注意：

- **自动去后缀**：若 `name` 带有 `.sql`、`.py`、`.ipynb` 等后缀，系统会自动将其裁切掉。
- **符号与大小写转换**：系统会自动将所有大写字母转为**小写**，并将所有下划线 `_` 转换为**中划线 `-`**。
- **非法字符拦截**：任务名最终必须符合正则 `^[a-z0-9]([-a-z0-9]*[a-z0-9])?$`，且最大长度不能超过 **25 个字符**。若包含特殊符号（如 `@`, `#`, `$`）或超长，系统会直接报错。
- _示例_：用户指定名称 `User_Data_ETL.sql` → 系统最终落地为 `user-data-etl`。

### 2. 任务名缺省（自动提取）逻辑

- 当 `isNew: true`（新建任务）且用户**未明确指定**任务名时：
- **不要瞎编，也不要强制追问**。直接将 `name` 留空 `""`。
- 底层 Skill 会自动解析 `node_path`，提取其最后的文件名，并应用上述清洗规则作为任务名。
- _示例_：`node_path` 为 `/jobs/sync_user_data.sql` → 系统自动生成任务名 `sync-user-data`。
- 更新任务时，只需传入需要修改的字段，未传字段保留原值。

### 3. ipynb 文件特殊处理

- 当 `node_path` 以 `.ipynb` 结尾时，系统会自动提取其中所有 Code Cell（代码单元格）的内容并填充至 `sql_details`，无需手动解析文件内容。

---

## Flink 任务（sql_engine: 0）

阅读 [references/flink-config.md](references/flink-config.md) 获取完整参数说明。

常用配置：

```json
{
  "isNew": true,
  "name": "",
  "description": "",
  "type": 0,
  "note_id": null,
  "revision_id": "v-1",
  "app_info": {
    "sql_engine": 0,
    "sql_info": {
      "node_path": "/path/to/job.sql",
      "node_label": "job.sql",
      "sql_details": "",
      "resource": "",
      "job_type": "stream",
      "checkpoint_interval": "300000",
      "parallelism": 1,
      "slots": 2,
      "memory_process_size": 2048,
      "memory_offheap_size": 128,
      "params": ""
    }
  }
}
```

**job_type 选择**：

- `stream`：实时流处理，持续运行，有状态，需要 checkpoint
- `batch`：有限数据集批处理，运行完即结束

---

## Spark 任务（sql_engine: 1）

阅读 [references/spark-config.md](references/spark-config.md) 获取完整参数说明。

常用配置：

```json
{
  "isNew": true,
  "name": "",
  "description": "",
  "type": 0,
  "note_id": null,
  "revision_id": "v-1",
  "app_info": {
    "sql_engine": 1,
    "sql_info": {
      "node_path": "/path/to/job.sql",
      "node_label": "job.sql",
      "sql_details": "",
      "resource": "",
      "job_type": "batch",
      "num_executors": 4,
      "executor_cores": 2,
      "executor_memory": [4, "G"],
      "driver_cores": 1,
      "driver_memory": [2, "G"],
      "params": ""
    }
  }
}
```

Spark 固定为 `job_type: batch`，不支持流处理。

---

## Python 任务（sql_engine: 2）

阅读 [references/python-config.md](references/python-config.md) 获取完整参数说明。

常用配置：

```json
{
  "isNew": true,
  "name": "",
  "description": "",
  "type": 0,
  "note_id": null,
  "revision_id": "v-1",
  "app_info": {
    "sql_engine": 2,
    "sql_info": {
      "node_path": "/path/to/script.py",
      "node_label": "script.py",
      "sql_details": "",
      "archives_package": "my-python-env",
      "resource": "",
      "job_type": "batch",
      "executor_cores": 2,
      "executor_memory": [4, "G"],
      "driver_cores": 1,
      "driver_memory": [2, "G"],
      "params": ""
    }
  }
}
```

提示：job_type 固定为 batch。`archives_package` 填包名或包 ID，需要先通过 `upload_package` 上传。如果使用 `.ipynb` 文件，系统会自动提取 code cell 内容作为执行代码。

---

## Ray 任务（sql_engine: 3）

RayJob 固定为批任务。创建前必须读取 [`ray-job`](../ray-job/SKILL.md)，由该 Skill 提供完整资源字段、RayJob 白名单配置、多文件工作目录打包和排障规则。

- 单文件任务直接把入口源码填入 `sql_details`，`aiTask.app_info.sql_info.runtime_env_package` 可留空。
- 多文件任务先以 `type: 7` 上传 ZIP，再把包名或 ID 填入 `aiTask.app_info.sql_info.runtime_env_package`。
- `driver_memory` 是 Ray Head Pod 内存，建议至少从 `4G` 起；不能照搬普通 Python 任务的 `2G` 默认值。
- 用户的 `ray_runtime_env_config` 不得设置 `working_dir`，该字段由平台生成。

---

## 调用 Tool

参数确认无误后，调用 `submit_approval` Tool 执行。

参数缺失时主动追问用户，不要猜测补全关键字段（如 node_path、引擎类型）。

---

## 典型场景

### 场景 A：新建 Flink 流任务（未明确指定任务名）

- **用户诉求**："帮我创建一个 Flink 流任务，读 /jobs/sync.sql，并行度设 4"
- **逻辑处理**：`isNew` 设为 `true`。用户未提供任务名，`name` 留空，系统将自动从 `node_path` 中提取 `sync.sql` 作为任务名。补充完整的 Flink 基础运行环境参数。

```json
{
  "isNew": true,
  "name": "",
  "description": "由 AI 协助创建的 Flink 流任务",
  "type": 0,
  "note_id": null,
  "revision_id": "v-1",
  "app_info": {
    "sql_engine": 0,
    "sql_info": {
      "node_path": "/jobs/sync.sql",
      "node_label": "sync.sql",
      "sql_details": "",
      "resource": "",
      "job_type": "stream",
      "checkpoint_interval": "300000",
      "parallelism": 4,
      "slots": 2,
      "memory_process_size": 2048,
      "memory_offheap_size": 128,
      "params": ""
    }
  }
}
```

### 场景 B：新建 Spark 批处理任务（显式指定任务名与透传参数）

用户诉求："写个名为 user_p1 的 Spark 批处理任务，路径是 /spark/etl.sql，设置执行器 8 个，参数：结束标志设 40000，限制数设 36000"

逻辑处理：isNew 设为 true。使用用户提供的 user_p1 作为 name。job_type 自动固化为 batch。params 严格按照 --key value 格式拼接。

```json
{
  "isNew": true,
  "name": "user_p1",
  "description": "Spark 批处理任务",
  "type": 0,
  "note_id": null,
  "revision_id": "v-1",
  "app_info": {
    "sql_engine": 1,
    "sql_info": {
      "node_path": "/spark/etl.sql",
      "node_label": "etl.sql",
      "sql_details": "",
      "resource": "",
      "job_type": "batch",
      "num_executors": 8,
      "executor_cores": 2,
      "executor_memory": [4, "G"],
      "driver_cores": 1,
      "driver_memory": [2, "G"],
      "params": "--nummarkEnd 40000 --nummarkLimit 36000"
    }
  }
}
```

### 场景 C：更新已有任务（通过任务名修改部分配置）

用户诉求："把 orders_sync 任务的并行度改成 8"

逻辑处理：isNew 设为 false。必须指定 name 为 orders_sync 以便系统检索。虽然更新只修改 parallelism，但保留原引擎（Flink）所需的完整框架参数骨架，防止底层合并策略引发未定义行为。

```json
{
  "isNew": false,
  "name": "orders_sync",
  "description": "",
  "type": 0,
  "note_id": null,
  "revision_id": "v-1",
  "app_info": {
    "sql_engine": 0,
    "sql_info": {
      "node_path": "",
      "node_label": "",
      "sql_details": "",
      "resource": "",
      "job_type": "stream",
      "checkpoint_interval": "300000",
      "parallelism": 8,
      "slots": 2,
      "memory_process_size": 2048,
      "memory_offheap_size": 128,
      "params": ""
    }
  }
}
```

---

## 常见问题

| 问题              | 原因                        | 解决方案                                 |
| ----------------- | --------------------------- | ---------------------------------------- |
| 找不到已发布任务  | name 拼写错误或任务未发布   | 确认任务已在生产环境发布，检查名称大小写 |
| Python 包解析失败 | archives_package 名称不存在 | 先调用 upload_package 上传，再创建任务   |
| ipynb 内容为空    | 文件没有 code cell          | 确认 .ipynb 文件中有代码单元格           |
