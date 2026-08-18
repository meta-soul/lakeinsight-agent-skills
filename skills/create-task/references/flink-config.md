# Flink 任务配置参考

> sql_engine = 0

## 完整参数说明

| 参数                | 类型              | 默认值   | 说明                                                                                                                                                                             |
| :------------------ | :---------------- | :------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| resource            | string            | ""       | 其他资源配置，通常留空。                                                                                                                                                         |
| job_type            | "stream"\|"batch" | "stream" | 任务类型。`stream` 代表实时流处理（持续运行、有状态，需开启 Checkpoint）；`batch` 代表有限数据集批处理。                                                                         |
| sql_details         | string            | ""       | SQL 内容详情。**通常保持留空 `""`**。系统会自动根据 `node_path` 读取文件内容并注入，调用端无需关注和传递具体 SQL 文本。                                                          |
| checkpoint_interval | string            | "300000" | Checkpoint 间隔（毫秒），流任务容错与状态恢复的关键参数。                                                                                                                        |
| parallelism         | number            | 1        | 并行度，直接影响任务的吞吐量和资源消耗。                                                                                                                                         |
| slots               | number            | 2        | TaskManager 槽位数，决定单个 TaskManager 上的并发线程数。                                                                                                                        |
| memory_process_size | number            | 2048     | TaskManager 进程总内存（MB）。                                                                                                                                                   |
| memory_offheap_size | number            | 128      | 堆外内存（MB），若使用 RocksDB 状态后端建议调大。                                                                                                                                |
| params              | string            | ""       | 自定义运行参数与动态配置透传项。<br>**格式要求**：`--key value`，多个配置项之间用**空格**分隔。<br>例如：`--nummarkEnd 40000 --nummarkLimit 36000`                               |
| node_path           | string            | 可选     | SQL 文件路径。**新建任务**时系统会自动读取文件内容，并从中自动提取文件名作为任务名（若未显式指定 `name`）。对于前端和 Tool 调用而言，**无需感知也无需传递 `sql_details` 字段**。 |
| node_label          | string            | 可选     | 文件名标签，通常与 `node_path` 中的文件名保持一致（如 `job.sql`）。                                                                                                              |

---

## 调优建议

**并行度（parallelism）**

- 低延迟场景：建议与 Source（如 Kafka）的分区数保持一致。
- 高吞吐场景：可调整为 Source 分区数的 2-4 倍。
- 建议从 2 开始调测，根据实际吞吐量和反压情况逐步调整。

**内存配置**

- 普通流任务：保持默认推荐即可（`memory_process_size = 2048`, `memory_offheap_size = 128`）。
- 有状态任务（使用 RocksDB 状态后端）：`memory_offheap_size` 建议调大至 512 - 2048。
- 大状态/高并发任务：`memory_process_size` 建议上调至 4096+。

**Checkpoint 间隔**

- 低延迟/高容错优先：设置为 `60000`（1分钟）。
- 吞吐量优先：设置为 `300000`（5分钟，系统默认值），减少频繁 Checkpoint 带来的性能损耗。
- 测试环境：若不需要状态容错，可设置极大的值来模拟关闭。

**自定义参数（params）使用规约**

- 必须遵循严格的空格分隔键值对格式。短横线 `--` 与参数名之间、参数名与参数值之间、多个参数组之间都**必须有且仅有一个空格**。

---

```json
{
  "app_info": {
    "sql_engine": 0,
    "sql_info": {
      "node_path": "/jobs/high_throughput.sql",
      "node_label": "high_throughput.sql",
      "sql_details": "",
      "resource": "",
      "job_type": "stream",
      "checkpoint_interval": "300000",
      "parallelism": 1,
      "slots": 2,
      "memory_process_size": 2048,
      "memory_offheap_size": 128,
      "params": "--nummarkEnd 40000 --nummarkLimit 36000"
    }
  }
}
```
