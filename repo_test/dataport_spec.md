# dataport_spec — DataPort I/O 适配层

> Status: active
> Authority: normative
> Read-Tier: task-scoped
> Purpose: DataPort 测试断言 — 验证 fetch/push 唯一 I/O 通道、SourceDescriptor 纯解析、CleanContext 废弃
> 依据: `work_memo/2026-06-03_PLAN_DATAPORT.md`、`DESIGN_ORCHESTRATOR.md`、`PENDING.md`
> 创建: 2026-06-03

---

## 一、模块定位

DataPort 是 orchestrator 的**唯一 I/O 通道**：

| 层 | 职责 | 接触什么 |
|----|------|---------|
| Resolver | 字符串 → `SourceDescriptor`（纯解析） | 不碰文件 |
| **DataPort** | **fetch() / push()** | **唯一碰文件的地方** |
| Engine / Planner | 纯数据变换 | 不碰文件 |

---

## 二、接口

### 2.1 SourceDescriptor

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

### 2.2 fetch()

```python
def fetch(desc: SourceDescriptor, intent: Intent) -> dict[str, Any]:
    """按描述符读取数据。按 source_type + intent 返回不同 clean dict 集合。"""
```

### 2.3 push()

```python
def push(desc: SourceDescriptor, intent: Intent, result: PipelineResult) -> None:
    """按描述符写入结果。仅 workspace + COMPUTE_MAPPING 需要持久化。"""
```

---

## 三、黑箱测试断言

### 3.1 DataPort 模块存在

| # | 断言 | 级别 |
|---|------|:---:|
| T-DP-01 | `orchestrator/data_port.py` 存在 `fetch()` 函数 | MUST |
| T-DP-02 | `orchestrator/data_port.py` 存在 `push()` 函数 | MUST |
| T-DP-03 | `orchestrator/__init__.py` 从 `data_port` import `fetch` / `push` | MUST |

### 3.2 SourceDescriptor 替代 CleanContext

| # | 断言 | 级别 |
|---|------|:---:|
| T-DP-04 | `orchestrator/resolver.py` 中 `WorkspaceResolver.resolve()` 返回 `SourceDescriptor`（而非 `CleanContext`），且**不包含** I/O 操作（不含 `wm.read_*`、`open()`、`load_json_file` 等） | MUST |
| T-DP-05 | `orchestrator/resolver.py` 中 `FilePathResolver.resolve()` 返回 `SourceDescriptor`，不含 I/O | MUST |
| T-DP-06 | `orchestrator/resolver.py` 中 `RawDictResolver.resolve()` 返回 `SourceDescriptor`，不含 I/O | MUST |
| T-DP-07 | `CleanContext` dataclass 不再存在于 `orchestrator/resolver.py` 中 | MUST |
| T-DP-08 | `plan_fileops()` 不再接受 `CleanContext` 参数——改为接受 DataPort.fetch() 返回的 dict | MUST |

### 3.3 fetch 行为

| # | 断言 | 级别 |
|---|------|:---:|
| T-DP-09 | `fetch(workspace, COMPUTE_MAPPING)` 返回 `{database, user_config, final_mapping, aggregated_rule_set, decisions}` | MUST |
| T-DP-10 | `fetch(workspace, BACKUP)` 返回 `{database, user_config, final_mapping}` | MUST |
| T-DP-11 | `fetch(file_paths, BACKUP)` 返回 `{database, user_config, final_mapping: []}` | MUST |
| T-DP-12 | `fetch(raw_dict, *)` 返回 `{database: desc.database_dict, ...}`（透传） | MUST |
| T-DP-13 | `database_name` 格式校验——`fetch()` 中校验 name 不含 `..` 等路径穿越字符 | MUST |

### 3.4 push 行为

| # | 断言 | 级别 |
|---|------|:---:|
| T-DP-14 | `push(workspace, COMPUTE_MAPPING, result)` 将 `result.mapping_result` 写入 workspace mapping 文件 | MUST |
| T-DP-15 | `push(workspace, COMPUTE_MAPPING, result)` 将 fingerprints（`kmmrule` / `database` sha256 + `computed_at`）写入 workspace | MUST |
| T-DP-16 | `push(workspace, COMPUTE_MAPPING, result)` 若 `result.trees` 非空，生成 SVG 并写入 workspace | MUST |
| T-DP-17 | `push(non-workspace, *, *)` / `push(*, non-COMPUTE_MAPPING, *)` 不执行任何写入 | MUST |

### 3.5 原语不经过 DataPort

| # | 断言 | 级别 |
|---|------|:---:|
| T-DP-18 | `data_port.py` 不 import `backup_ops`、`restore_ops`、`apply_ops` | MUST |
| T-DP-19 | 原语的 `__all__` 中不含 DataPort 相关符号 | MUST |

### 3.6 文档一致性

| # | 断言 | 级别 |
|---|------|:---:|
| T-DP-20 | `DESIGN_ORCHESTRATOR.md` 描述 DataPort 作为独立模块 | MUST |
| T-DP-21 | `DESIGN_PLANNER.md` 描述 dispatch 流程含 `DataPort.fetch/push` 步骤 | MUST |

---

## 四、验收标准

- [ ] 全部 T-DP-01 ~ T-DP-21 通过
- [ ] `dispatch()` 流程：Resolver.resolve → DataPort.fetch → Engine/Planner → DataPort.push
- [ ] `CleanContext` 不再存在于代码库中（历史文档除外）
- [ ] 现有测试在接口适配后通过
