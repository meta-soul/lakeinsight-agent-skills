---
name: ray-job
description: |
  在 LakeInsight 配置和排查 KubeRay RayJob 时使用。
  覆盖 sql_engine=3、单文件与多文件 runtime_env 包、RayJob 原生配置、worker 自动扩缩容、Daft Ray runner 与常见部署故障。
---

# LakeInsight RayJob

## 使用前检查

RayJob 只能在 Kubernetes 计算引擎且后端能力接口返回可用时创建。后端按以下顺序检查：

1. 数据库配置 `compute_engine_capabilities.ray_enabled` 是否为 `true`；关闭时不访问 Kubernetes；
2. LakeInsight 是否为 Kubernetes compute-engine mode；
3. `rayjobs.ray.io` CRD 是否存在且当前身份可访问；
4. 带标签 `app.kubernetes.io/name=kuberay-operator` 的 Deployment 是否至少有一个 `availableReplicas > 0`。

以下状态都不能提交 RayJob：CRD 缺失、RBAC 403、Operator 未就绪、数据库显式禁用、或平台不在 Kubernetes compute-engine mode。

## 任务模型

LakeInsight Ray 数据开发任务使用 `sql_engine: 3`，固定为批任务。主脚本内容来自 `sql_info.sql_details`，平台会生成入口文件：

```text
<任务名称>.py
```

定时调度实例会在任务名称后追加实例 ID 和 `-batch`。

再把它和可选 runtime_env 包合并为一个 ZIP，上传对象存储，并作为 Ray `runtimeEnvYAML.working_dir`。不要在用户 YAML 中设置 `working_dir`，平台会拒绝覆盖。

`num_executors` 是 Ray worker 副本数，不是 Spark executor。`executor_*` 对应每个 worker pod；`driver_*` 对应 Ray head pod。

Head 同时承载 Ray GCS、Dashboard、Job Server 和任务 driver 等组件，通常比单个 worker 需要更多内存。`driver_memory` 建议从 `4G` 起配；Daft、大规模元数据或高并发任务可从 `8G` 起，并根据实际使用量调整。若 Head 反复出现退出码 137、`OOMKilled`，或伴随内存不足的 503 探针失败，应优先增大 `driver_memory`，不能只重启 Pod。

当前 `lakeinsight-mcp` 的 `submit_approval` schema 只接受 Flink、Spark 和 Python（`sql_engine` 为 0、1、2）；尚不能通过该 Tool 创建 `sql_engine: 3` 的 RayJob。不要生成一个会被 MCP 参数校验拒绝的 Ray 创建调用；Ray 创建 MCP 支持补齐前，通过 LakeInsight UI 或后端任务接口配置。

## runtime_env 包

runtime_env 包必须是 `.zip`。在 LakeInsight UI 上传时选择 Ray runtime-env 包类型；平台会下载、解压并和自动生成的入口脚本合并。约束是：

- ZIP 内不能包含平台将生成的 `<job-name>.py`，否则入口文件冲突；
- 不要上传密钥、kubeconfig、虚拟环境缓存或不必要的二进制产物；
- `ray_runtime_env_config` 不能包含 `working_dir`。

`ray_runtime_env_config` 是 YAML。`excludes` 使用 gitwildmatch 模式并在重新打包前应用，不能排除平台入口文件；其余字段进入 Ray `runtimeEnvYAML`。

多 Python 文件任务实际执行的代码来自任务编辑器中的 `sql_details`。用户本地项目可以包含 `entrypoint.py`，但新建任务时前端默认用所选文件名生成任务名称，后端又用任务名称生成运行入口；因此默认不要把 `entrypoint.py` 压入 runtime_env ZIP，只压入口依赖的模块和资源。需要生成或检查这种包时，读取[多文件 runtime_env 示例](references/multifile-runtime-env.md)，并优先复用其中的完整样例文件。

若 `ray_runtime_env_config` 使用 `pip` 或 `uv` 安装额外依赖，Head 和 Worker 必须能访问对应包索引；完全隔离网络时使用预装依赖的 runtime 镜像。具体 YAML 见多文件示例。

当前 `lakeinsight-mcp` 的 `upload_package` 只接受类型 0–6，不能上传 Ray runtime-env 的后端类型 7；不要把普通 Python Archives 当作 Ray runtime-env 包。

## Worker 自动扩缩容

```json
{
  "worker_autoscaling": true,
  "num_executors": 1,
  "worker_max_replicas": 5
}
```

启用时，LakeInsight 创建的 Ray worker group 为：

```text
replicas = 0
minReplicas = 0
maxReplicas = worker_max_replicas
enableInTreeAutoscaling = true
```

脚本必须产生有资源请求的并行任务，才能触发扩容：

```python
import ray
import time
import socket

ray.init(address="auto")

@ray.remote(num_cpus=1)
def work(index):
    print(f"task {index} on {socket.gethostname()}", flush=True)
    time.sleep(60)

ray.get([work.remote(index) for index in range(10)])
```

不要用 `num_cpus=0.1` 验证 CPU 扩容：大量任务可能在少量 worker 上排队或触发内存压力，不能证明 autoscaler 工作正常。

## RayJob 原生配置

`ray_job_config` 仅接受以下 LakeInsight 白名单字段，不会透传任意 KubeRay spec：

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `activeDeadlineSeconds` | 整数 | RayJob 总运行期限 |
| `backoffLimit` | 整数 | RayJob 顶层重试次数 |
| `preRunningDeadlineSeconds` | 整数 | Job 进入 Running 前允许等待的期限 |
| `ttlSecondsAfterFinished` | 整数 | 任务结束后保留 RayJob 的时间 |
| `shutdownAfterJobFinishes` | 布尔值 | Job 结束后是否关闭 RayCluster |
| `submitterConfig.backoffLimit` | 整数 | submitter Kubernetes Job 的重试次数 |

推荐使用 YAML mapping：

```yaml
activeDeadlineSeconds: 3600
preRunningDeadlineSeconds: 600
ttlSecondsAfterFinished: 300
shutdownAfterJobFinishes: true
backoffLimit: 0
submitterConfig:
  backoffLimit: 0
```

也支持空格分隔的 `key=value` 形式，但这种形式无法表达 `submitterConfig` mapping。布尔值必须写成 `true` 或 `false`。`timeout_seconds` 是 LakeInsight 的便捷字段：未填写 `ray_job_config` 时，它会转换为 `activeDeadlineSeconds`；一旦填写 `ray_job_config`，应直接在其中配置期限。

不要通过 `ray_job_config` 覆盖平台负责的入口命令、`runtimeEnvYAML.working_dir`、用户凭据或核心资源模板。

## Daft on Ray

Daft 连接 Ray 集群、LakeSoul 读取/写入、谓词下推、分区和小文件规则均由 `daft-lakesoul` skill 负责。RayJob 只负责提供集群、镜像和 Worker 资源。

## 运行和排障顺序

1. 查看 RayJob CR：`kubectl get rayjobs -n <workspace>`。
2. 查看 Head、Worker、Submitter pod；RayJob 可能已创建但 submitter 连接 Head dashboard `:8265` 过早而失败。
3. Head Service 有 endpoint 且 Head 的 dashboard/job submission server 已监听后，才应执行 `ray job logs` 或 `ray job status`。
4. 查看 RayJob status、submitter pod 日志、head pod 日志、worker `raylet.out`。
5. 若 worker 被 Ray OOM monitor 杀死，增加 pod memory 或提高每任务 `num_cpus`/降低并发；不要先关闭内存监控。
