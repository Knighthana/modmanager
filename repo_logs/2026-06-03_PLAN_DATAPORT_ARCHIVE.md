# PLAN_DATAPORT — I/O 适配层

> 创建日期：2026-06-03
> 状态：confirmed
> 最新更新：2026-06-03 — SourceDescriptor/DestDescriptor 分离，TaskRequest 扩展 output_type
> 关联：`work_memo/2026-06-03_PENDING.md`、`repo_test/dataport_spec.md`

---

## 一、目的

在 orchestrator 中插入一个 **DataPort** 模块，作为系统与外界之间的**唯一 I/O 通道**。Fetch 来源与 Push 目标通过不同的描述符显式指定，互不混用。

```
调用方（Web / CLI）构造 TaskRequest
      │  ├─ resolver_type + resolver_args  →  来源格式
      │  └─ output_type   + output_args    →  目标格式
      ▼
  dispatch(TaskRequest)
      │
      ├─ 1. Resolver.resolve(task)
      │     ┌─ 纯解析：字符串 → SourceDescriptor（fetch 来源）
      │     └─ 产出 SourceDescriptor
      ├─ 2. DataPort.fetch(SourceDescriptor, intent)
      │     ┌─ 纯 I/O：读文件 / 读 DB / 读缓存
      │     └─ 产出 clean dicts
      ├─ 3. Engine / Planner
      │     ┌─ 纯数据变换
      │     └─ 不碰文件
      ├─ 4. DataPort.push(DestDescriptor, intent, result)   ← 根据 output_type 决定
      │     ┌─ output_type="workspace" + COMPUTE_MAPPING → 写回
      │     └─ output_type="none" → 跳过
      ▼
  PipelineResult → 返回调用方
```

---

## 二、模块定位

| 层 | 职责 | 接触什么 |
|----|------|---------|
| Resolver | 字符串 → SourceDescriptor（纯解析） | 不碰文件 |
| **DataPort** | fetch(DestDescriptor) / push(DestDescriptor) | **唯一碰文件的地方** |
| Engine / Planner | 纯数据变换 | 不碰文件 |
| 原语（backup_ops 等） | 操作业务文件（mod 文件、备份文件） | 碰业务文件，不过 DataPort |

> 边界：Steam 作为 OS 文件系统目录——原语直接操作业务文件，不走 DataPort。

---

## 三、文件位置

```
src/modmgr/orchestrator/
├── __init__.py          ← dispatch() 路由 + TaskRequest/PipelineResult
├── _common.py
├── entry.py             ← Intent, TaskRequest（含 output_type/output_args）
├── resolver.py          ← Resolver 策略（纯解析，产 SourceDescriptor）
├── data_port.py         ← 【新】DataPort: SourceDescriptor/DestDescriptor + fetch()/push()
├── verifier.py          ← 规则校验
├── compute_pipeline.py  ← compute 引擎
└── fileops/
    ├── __init__.py      ← execute() 统一入口
    ├── _common.py       ← _notify 等共享辅助
    └── planner/
        ├── __init__.py
        ├── planner.py       ← plan_fileops() + FileOpsPlan
        ├── preflight.py     ← 门禁检查
        └── ignore_rules.py  ← .kmmignore 解析
```

---

## 四、核心接口

### 4.1 TaskRequest

```python
@dataclass
class TaskRequest:
    identity: Literal["web", "cli"]
    intent: Intent
    resolver_type: Literal["workspace", "file_paths", "raw_dict"]
    resolver_args: dict[str, Any]                              # fetch 来源参数
    output_type: Literal["workspace", "none"] = "none"          # push 目标类型
    output_args: dict[str, Any] = field(default_factory=dict)   # push 目标参数
    flags: dict[str, Any] = field(default_factory=dict)
```

Web workspace compute 示例：
```python
TaskRequest(
    identity="web",
    intent=Intent.COMPUTE_MAPPING,
    resolver_type="workspace",
    resolver_args={"workspace_id": "abc", "config_index": "/path/to/config"},
    output_type="workspace",
    output_args={"workspace_id": "abc", "config_index": "/path/to/config"},
)
```

### 4.2 SourceDescriptor

Resolver 产出，描述 fetch 来源：

```python
@dataclass
class SourceDescriptor:
    source_type: Literal["workspace", "file_paths", "raw_dict"]
    workspace_id: str | None = None
    config_index: str = ""
    database_path: str | None = None
    database_dict: dict | None = None
    aggregated_rule_set: dict | None = None
```

### 4.3 DestDescriptor

从 TaskRequest.output_type + output_args 构建，描述 push 目标：

```python
@dataclass
class DestDescriptor:
    output_type: Literal["workspace", "none"]
    workspace_id: str | None = None
    config_index: str = ""
```

### 4.4 DataPort.fetch()

```python
def fetch(desc: SourceDescriptor, intent: Intent) -> dict[str, Any]:
    """按 SourceDescriptor 读取数据，返回 clean dicts。

    Returns:
        {
            "database": {...},
            "user_config": {...},
            "final_mapping": [...],
            "aggregated_rule_set": {...},  # workspace compute 时
            "decisions": {...},             # workspace compute 时
            # ... 按 intent 不同，返回不同 key 集合
        }
    """
```

### 4.5 DataPort.push()

```python
def push(dest: DestDescriptor, intent: Intent, result: PipelineResult) -> None:
    """按 DestDescriptor 写入结果。

    - dest.output_type == "workspace" ∧ intent == COMPUTE_MAPPING → 写 mapping/SVG/fingerprints
    - 其他组合 → 无操作
    """
```

---

## 五、SourceDescriptor/DestDescriptor 填充规则

### SourceDescriptor 按 resolver_type

| resolver_type | 字段 | 来源 |
|---------------|------|------|
| `"workspace"` | `workspace_id` | `resolver_args["workspace_id"]` |
| | `config_index` | `resolver_args.get("config_index")` |
| `"file_paths"` | `database_path` | `resolver_args["database_path"]` |
| | `config_index` | `resolver_args.get("config_index")` |
| `"raw_dict"` | `database_dict` | `resolver_args["database"]` |
| | `aggregated_rule_set` | `resolver_args.get("aggregated_rule_set")` |

### DestDescriptor 按 output_type

| output_type | 字段 | 来源 |
|-------------|------|------|
| `"workspace"` | `workspace_id` | `output_args["workspace_id"]` |
| | `config_index` | `output_args.get("config_index")` |
| `"none"` | — | 不执行 push |

---

## 六、DataPort.fetch() 行为

### workspace + COMPUTE_MAPPING

```
fetch():
  1. 读 user_config（via config_index）
  2. new WorkspaceManager → read_meta(workspace_id) → database_name
  3. 解析 database_name → database_path，读 database 文件
  4. read_mapping(workspace_id) → final_mapping
  5. read_aggregated_rule(workspace_id) → aggregated_rule_set
  6. read_decisions(workspace_id) → decisions
  → return {database, user_config, final_mapping, aggregated_rule_set, decisions}
```

### workspace + BACKUP/APPLY/RESTORE/RUN

```
fetch():
  1. 读 user_config
  2. new WorkspaceManager → read_meta → database_name
  3. 解析 database_name → database_path，读 database
  4. read_mapping → final_mapping
  → return {database, user_config, final_mapping}
```

### file_paths + BACKUP/APPLY/RESTORE/RUN

```
fetch():
  1. 读 database_path → database
  2. 读 config_index → user_config
  → return {database, user_config, final_mapping: []}
```

### raw_dict + any intent

```
fetch():
  → return {database: desc.database_dict, 
            user_config: {},
            final_mapping: [], 
            ... (desc 中已有的其他字段透传)}
```

---

## 七、DataPort.push() 行为

| output_type | intent | 行为 |
|:-----------:|--------|------|
| `"workspace"` | COMPUTE_MAPPING | 写 mapping/SVG/fingerprints 到 workspace |
| `"workspace"` | 其他 | 无操作 |
| `"none"` | 任意 | 无操作 |

---

## 八、dispatch() 流程

```python
def dispatch(request, *, on_progress=None):
    # 1. Resolver 产 SourceDescriptor（纯解析）
    resolver = _select_resolver(request.resolver_type)
    fetch_desc = resolver.resolve(request)
    
    # 2. DataPort 产 clean dicts（唯一 I/O 入口）
    data = data_port.fetch(fetch_desc, request.intent)
    
    # 3. Engine / Planner
    if request.intent == Intent.COMPUTE_MAPPING:
        result = _dispatch_compute(data, on_progress)
    else:
        result = fileops.execute(data, request.intent, request.flags, on_progress)
    
    # 4. DataPort push（从 TaskRequest 构建 DestDescriptor）
    push_desc = DestDescriptor(
        output_type=request.output_type,
        workspace_id=request.output_args.get("workspace_id"),
        config_index=request.output_args.get("config_index", ""),
    )
    data_port.push(push_desc, request.intent, result)
    
    return result
```

---

## 九、对现有代码的影响

### 9.1 Resolver 重写为纯解析

当前 `WorkspaceResolver.resolve()` 做了大量 I/O（读 meta、读 mapping、读数据库）。改为只产出 `SourceDescriptor`：

```python
# 旧
class WorkspaceResolver:
    def resolve(self, request) -> CleanContext:
        meta = wm.read_meta(...)           # I/O
        database = _resolve_database(...)   # I/O
        return CleanContext(...)

# 新
class WorkspaceResolver:
    def resolve(self, request) -> SourceDescriptor:
        return SourceDescriptor(
            source_type="workspace",
            workspace_id=request.resolver_args["workspace_id"],
            config_index=request.resolver_args.get("config_index", ""),
        )
```

### 9.2 CleanContext 废弃

`CleanContext` dataclass 删除。`plan_fileops(context, ...)` → `plan_fileops(data, ...)`，其中 `data` 是 `DataPort.fetch()` 返回的 dict。

### 9.3 plan_fileops 适配

```python
# 旧
def plan_fileops(request, context: CleanContext, ...):
    context.final_mapping → data["final_mapping"]
    context.database      → data["database"]
    context.user_config   → data["user_config"]

# 新
def plan_fileops(request, data: dict, ...):
    data["final_mapping"]
    data["database"]
    data["user_config"]
```

---

## 十、状态

| # | 议题 | 状态 |
|---|------|:---:|
| P1 | .kmmignore 原地规则 | ✅ resolved（不搬动不拷贝） |
| D1 | DataPort 实现（含 SourceDescriptor/DestDescriptor 分离） | ✅ SPEC 完成（`repo_test/dataport_spec.md`），待 smith 实现 |
| C1 | compute_ws 废除 + 入口修正 | ✅ 已裁决，纳入任务卡 |
| W1 | Web 路由合规测试 | 待 probe 实现 |
| A1-A3 | fileops 目录重构 | ✅ 已裁决，纳入任务卡 |

### .kmmignore 与 DataPort 的关系

`.kmmignore` 属于 Planner 的纯数据变换（读取盘上文件 → 解析 → 过滤规则）。不经过 DataPort——它是用户编辑的业务规则文件，不是系统配置/中间结果。原地规则：不随任何操作移动。
