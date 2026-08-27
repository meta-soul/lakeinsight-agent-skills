# 多 Python 文件 runtime_env 示例

本例验证 LakeInsight 将任务入口与用户上传的 Python 包合并后，KubeRay 能从多个模块读取 LakeSoul 数据。

任务编辑器中的 `sql_details` 是入口，上传 ZIP 只提供入口导入的模块。平台会将二者合并为 Ray working_dir，因此 ZIP 中不要包含 `<normalized-job-name>.py`；同名文件会导致合并失败。

## 可复用样例

完整文件位于 [`../assets/multifile-runtime-env/`](../assets/multifile-runtime-env/)：

```text
multifile-runtime-env/
|-- task_entry.py                 粘贴到 LakeInsight 任务内容，不放进 ZIP
`-- runtime-package/              只压缩这个目录中的内容
    |-- app/
    |   |-- __init__.py
    |   |-- config.py
    |   `-- reader.py
    `-- utils/
        |-- __init__.py
        `-- output.py
```

`task_entry.py` 使用 `parse_known_args()`，因此 LakeInsight 调度参数不会让 `argparse` 因未知参数直接退出。它连接平台创建的 Ray 集群，启用 Daft Ray runner，再调用 ZIP 中的模块。

## 打包

进入 `runtime-package` 后压缩其内容，使 `app/` 和 `utils/` 位于 ZIP 根目录：

```bash
cd skills/ray-job/assets/multifile-runtime-env/runtime-package
zip -r ../ray-runtime-multifile.zip app utils \
  -x '*/__pycache__/*' '*.pyc'
unzip -l ../ray-runtime-multifile.zip
```

正确的 ZIP 根目录应是：

```text
app/__init__.py
app/config.py
app/reader.py
utils/__init__.py
utils/output.py
```

不要在父目录执行 `zip -r ray-runtime-multifile.zip runtime-package`，否则会额外带一层目录。当前平台能够自动展开唯一的顶层目录，但直接使用正确根布局更容易检查，也不依赖该兼容行为。

## 创建任务

1. 把 `ray-runtime-multifile.zip` 上传为 Ray runtime-env 包。
2. 新建 `sql_engine: 3` 的批任务，把 `task_entry.py` 内容作为任务内容。
3. 将上传结果的真实 ID 写入 `runtime_env_package.id`。
4. 可在任务参数中填写：

```text
--namespace czods --table user --limit 5 --batch-size 256 --thread-count 1
```

5. 首次验证使用固定 Worker；读取成功后再单独测试自动扩缩容。

在 UI 中选择上传得到的 runtime-env 包、填入上述参数，并用 `excludes` 排除 `__pycache__` 与 `.pyc`。成功日志会包含表名、Daft schema 和 `rows` 字典。

## 添加第三方依赖

如果模块还依赖镜像中不存在的包，可配置 Ray runtime env：

```yaml
env_vars:
  PIP_INDEX_URL: https://pypi.internal.example/simple
  UV_INDEX_URL: https://pypi.internal.example/simple
uv:
  packages:
    - pendulum==3.0.0
  uv_check: false
  uv_pip_install_options:
    - --no-cache
excludes:
  - "**/__pycache__/**"
  - "**/*.pyc"
```

这会在 Ray runtime setup 阶段访问包索引。完全隔离网络且没有内部镜像时，不能依靠 `uv` 动态安装；应改用预装依赖的 runtime 镜像。

## 常见失败

- `ModuleNotFoundError: app`：ZIP 根目录不正确，或 `app/` 被 `excludes` 排除。
- `already contains entry file`：上传 ZIP 含有平台将生成的任务入口文件。
- `argparse: unrecognized arguments`：入口使用了 `parse_args()`；平台任务应使用 `parse_known_args()` 或显式声明所有调度参数。
- runtime env setup 下载超时：Pod 无法访问 PyPI/内部镜像，不是 working_dir ZIP 失效。
- Head 能导入但 Worker 不能导入：依赖只存在于 Head 的临时环境或挂载中；Head 和 Worker 应使用相同 runtime 镜像及 runtime env。
