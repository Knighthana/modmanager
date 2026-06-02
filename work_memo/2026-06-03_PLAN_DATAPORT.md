# PLAN_DATAPORT — I/O 适配层

> 创建日期：2026-06-03
> 状态：draft（待确认后转 SPEC）
> 关联：`work_memo/2026-06-03_PENDING.md`

---

## 一、目的

在 orchestrator 中插入一个 **DataPort** 模块，作为系统与外界之间的**唯一 I/O 通道**。它紧密贴合 Resolver，消费 Resolver 产出的语义描述符，执行具体的 fetch（读取）和 push（写入）操作。

```
调用方（Web / CLI）
      │
      ▼
  dispatch(TaskRequest)
      │
      ▼
  Resolver.resolve(task)
      │  ┌─ 纯解析：字符串 → 语义描述符
      │  │  不碰文件 / 网络 / DB
      │  └─ 产出 SourceDescriptor
      ▼
  DataPort.fetch(descriptor)
      │  ┌─ 纯 I/O：读文件 / 读 DB / 读缓存
      │  └─ 产出 clean dicts
      ▼
  Engine / Planner
      │  ┌─ 纯数据变换
      │  └─ 不碰文件
      ▼
  DataPort.push(descriptor, result)   ← 仅在需要持久化时
      │
      ▼
  PipelineResult → 返回调用方
```

---

## 二、模块定位

| 层 | 职责 | 接触什么 |
|----|------|---------|
| Resolver | 字符串 → 语义描述符（SourceDescriptor） | 不碰文件 |
| **DataPort** | 按描述符 fetch 数据 / push 结果 | **唯一碰文件的地方** |
| Engine / Planner | 纯数据变换 | 不碰文件 |
| 原语（backup_ops 等） | 操作业务文件（mod 文件、备份文件） | 碰业务文件，不过 DataPort |

> 边界：Steam 作为 OS 文件系统目录——原语直接操作业务文件，不走 DataPort。

---

## 三、文件位置

```
src/modmgr/orchestrator/
├── __init__.py          ← dispatch() 路由 + TaskRequest/PipelineResult
├── _common.py
├── entry.py             ← Intent, TaskRequest（扩展 output_spec）
├── resolver.py          ← Resolver 策略（纯解析）
├── data_port.py         ← 【新】DataPort: fetch() + push()
├── verifier.py          ← 规则校验
├── compute_pipeline.py  ← compute 引擎
└── fileops/
    ├── __init__.py      ← execute() 统一入口
    ├── planner.py       ← 当前 planner_fileops.py
    ├── preflight.py     ← 从当前 preflight.py 迁入
    ├── prep.py
    ├── backup_ops.py    ← 未来从 src/modmgr/backup_ops.py 迁入（裁定10）
    ├── restore_ops.py   ← 未来从 src/modmgr/restore_ops.py 迁入
    └── apply_ops.py     ← 未来从 src/modmgr/apply_ops.py 迁入
```

---

## 四、核心接口

### 4.1 SourceDescriptor

Resolver 产出，描述"从哪里取什么"：

```python
@dataclass
class SourceDescriptor:
    """Resolver 产出——语义描述符，不包含任何 I/O 结果。"""
    
    # 来源类型
    source_type: Literal["workspace", "file_paths", "raw_dict"]
    
    # Workspace 来源
    workspace_id: str | None = None
    config_index: str = ""
    
    # File paths 来源
    database_path: str | None = None
    
    # Raw dict 来源（CLI 直传，DataPort 直接回吐）
    database_dict: dict | None = None
    aggregated_rule_set: dict | None = None
    
    # 通用
    extra: dict[str, Any] = field(default_factory=dict)
```

### 4.2 DataPort.fetch()

```python
def fetch(desc: SourceDescriptor, intent: Intent) -> dict[str, Any]:
    """按描述符读取数据，返回 clean dicts。
    
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

### 4.3 DataPort.push()

```python
def push(desc: SourceDescriptor, intent: Intent, result: PipelineResult) -> None:
    """按描述符写入结果。
    
    仅在 intent 需要持久化时调用（如 compute 写 mapping/SVG 回 workspace）。
    不需要持久化的 intent（如 CLI raw_dict compute）跳过。
    """
```

---

## 五、对现有代码的影响

### 5.1 Resolver 需重写

当前 `WorkspaceResolver.resolve()` 做了大量 I/O（读 meta、读 mapping、读数据库）。改为只产出 SourceDescriptor：

```python
# 旧（resolver 自己做 I/O）
class WorkspaceResolver:
    def resolve(self, request) -> CleanContext:
        workspace_id = request.resolver_args["workspace_id"]
        wm = WorkspaceManager(...)
        meta = wm.read_meta(workspace_id)        # ← I/O
        database = _resolve_database(...)          # ← I/O
        mapping = wm.read_mapping(workspace_id)   # ← I/O
        return CleanContext(...)

# 新（resolver 只解析）
class WorkspaceResolver:
    def resolve(self, request) -> SourceDescriptor:
        workspace_id = request.resolver_args["workspace_id"]
        config_index = request.resolver_args.get("config_index", "")
        return SourceDescriptor(
            source_type="workspace",
            workspace_id=workspace_id,
            config_index=config_index,
        )
```

### 5.2 dispatch() 流程变更

```python
def dispatch(request, *, on_progress=None):
    # 1. 选 resolver，解析 → SourceDescriptor
    resolver = _select_resolver(request.resolver_type)
    desc = resolver.resolve(request)
    
    # 2. DataPort fetch → clean dicts
    data = data_port.fetch(desc, request.intent)
    
    # 3. 按 intent 路由到 engine / planner
    if request.intent == Intent.COMPUTE_MAPPING:
        result = _dispatch_compute(data, on_progress)
    else:
        result = fileops.execute(data, request.intent, request.flags, on_progress)
    
    # 4. 若需要持久化，DataPort push
    if _needs_persist(request.intent, desc):
        data_port.push(desc, request.intent, result)
    
    return result
```

### 5.3 CleanContext → 废弃

`CleanContext` dataclass 被 `SourceDescriptor` + DataPort fetch 的返回 dict 取代。不同 intent 得到不同的 clean dict 集合。

### 5.4 需要持久化判断

| Intent | workspace | file_paths | raw_dict |
|--------|:---------:|:----------:|:--------:|
| COMPUTE_MAPPING | ✓（写 mapping/SVG） | ✗ | ✗ |
| BACKUP | ✗（原语直接写） | ✗ | ✗ |
| APPLY | ✗ | ✗ | ✗ |
| RESTORE | ✗ | ✗ | ✗ |
| RUN | ✗ | ✗ | ✗ |

仅 workspace compute 需要 DataPort.push()。fileops 的结果本身就是原语操作业务文件，不需要 DataPort 写回。

---

## 六、SourceDescriptor 按 source_type 填充规则

| source_type | 字段 | 来源 |
|-------------|------|------|
| `"workspace"` | `workspace_id` | `resolver_args["workspace_id"]` |
| | `config_index` | `resolver_args.get("config_index")` |
| `"file_paths"` | `database_path` | `resolver_args["database_path"]` |
| | `config_index` | `resolver_args.get("config_index")` |
| `"raw_dict"` | `database_dict` | `resolver_args["database"]` |
| | `aggregated_rule_set` | `resolver_args.get("aggregated_rule_set")` |

## 七、DataPort.fetch() 按 source_type + intent 的行为

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

## 八、待确认

| # | 议题 | 状态 |
|---|------|:---:|
| P1 | 原语接口改造方案（.kmmignore 工单化）——与 DataPort 无关，仍待裁定 | open |
| W1 | Web 路由合规测试——与 DataPort 无关，仍待执行 | open |
| A1-A3 | fileops 目录重构——与 DataPort 方向一致，细节见 §三 | 已裁决 |
| C1a-c | Clean 上下文 + 回写 + 出口解耦——全部被 DataPort 解决 | ✅ resolved |
