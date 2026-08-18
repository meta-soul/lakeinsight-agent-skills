# Spark 任务配置参考

> sql_engine = 1，固定 job_type = "batch"

## 完整参数说明

| 参数            | 类型          | 默认值   | 说明                                                                                                                                                                               |
| :-------------- | :------------ | :------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| resource        | string        | ""       | 其他资源配置,通常留空。                                                                                                                                                            |
| job_type        | "batch"       | "batch"  | 任务类型。**固定为 `batch`(批处理)**,不支持流处理。                                                                                                                                |
| sql_details     | string        | ""       | SQL 内容详情。**通常保持留空 `""`**。系统会自动根据 `node_path` 读取文件内容并注入,调用端无需关注和传递具体 SQL 文本。                                                             |
| num_executors   | number        | 4        | 执行器(Executor)数量。                                                                                                                                                             |
| executor_cores  | number        | 2        | 每个执行器的 CPU 核心数。                                                                                                                                                          |
| executor_memory | [number, "G"] | [4, "G"] | 每个执行器的内存大小。格式为固定数组,如 `[4, "G"]`。                                                                                                                               |
| driver_cores    | number        | 1        | 驱动器(Driver)的 CPU 核心数。                                                                                                                                                      |
| driver_memory   | [number, "G"] | [2, "G"] | 驱动器的内存大小。格式为固定数组,如 `[2, "G"]`。                                                                                                                                   |
| params          | string        | ""       | 自定义运行参数与动态配置透传项。<br>**格式要求**:`--key value`,多个配置项之间用**空格**分隔。<br>例如:`--nummarkEnd 40000 --nummarkLimit 36000`                                    |
| node_path       | string        | 可选     | Spark SQL 文件路径。**新建任务**时系统会自动读取文件内容,并从中自动提取文件名作为任务名(若未显式指定 `name`)。对于前端和 Tool 调用而言,**无需感知也无需传递 `sql_details` 字段**。 |
| node_label      | string        | 可选     | 文件名标签,通常与 `node_path` 中的文件名保持一致(如 `job.sql`)。                                                                                                                   |

---

## 示例：大规模批处理

```json
{
  "app_info": {
    "sql_engine": 1,
    "sql_info": {
      "resource": "",
      "job_type": "batch",
      "sql_details": "",
      "num_executors": 4,
      "executor_cores": 2,
      "executor_memory": [4, "G"],
      "driver_cores": 1,
      "driver_memory": [2, "G"],
      "params": "--nummarkEnd 40000 --nummarkLimit 36000",
      "node_path": "/jobs/etl_daily.sql",
      "node_label": "etl_daily.sql"
    }
  }
}
```
