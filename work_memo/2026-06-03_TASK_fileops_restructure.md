## Task-Card: fileops 目录重构 + compute 修正 + DataPort 实现

**目标**
1. 先删旧代码，再按文档重构。不修补旧代码，不保留兼容占位
2. DataPort I/O 适配层实现：Resolver 纯解析化、CleanContext 废弃、fetch/push 唯一 I/O 通道
3. fileops 目录结构创建、Planner 入口统一、preflight/ignore_rules 归位、kmmignore 遗留代码删除
4. compute 入口修正：删除 `compute_ws` 和 `_dispatch_compute`，compute 走 `dispatch → Resolver → DataPort → Engine → DataPort.push` 全链路

**执行顺序**（每一步完成后只跑单元测试；全部完成后跑集成测试）
```
K1(删kmmignore死代码) → A1+A3(目录+文件移动) → A2(dispatch拆分) → D1(DataPort) → C1(compute)
```

**L1 硬约束**
- [ ] L1-1 先删旧再建新——死代码、旧路径、废弃类型一律先删除再重构
- [ ] L1-2 不留兼容占位文件。旧路径引用全局一步到位
- [ ] L1-3 原语之间互不知晓，不感知 `.kmmignore` / gate 逻辑
- [ ] L1-4 import 保持最小必要原则
- [ ] L1-5 拆分提交：每个阶段独立 commit，附带该阶段单元测试
- [ ] L1-6 集成测试在全部阶段完成后执行；若失败由 arch 分析设计冲突

## 接口契约（实现前定稿，smith 按此实现。设计问题不留到开工后）

### plan_fileops()

```python
def plan_fileops(
    request: TaskRequest,
    data: dict,              # DataPort.fetch() 返回的 clean dict
    *,
    on_progress: Any = None,
) -> FileOpsPlan:
```

**`data` dict 结构**（BACKUP/APPLY/RESTORE/RUN 通用）：

```python
{
    "database": { ... },          # database dict
    "user_config": { ... },       # user_config dict
    "final_mapping": [ ... ],     # list of {path, game_name, ...}
}
```

> COMPUTE_MAPPING 不走 `plan_fileops()`，compute 走 `compute(data)`。

### fileops.execute()

```python
def execute(
    data: dict,              # 同上
    intent: Intent,
    flags: dict,
    *,
    on_progress: Any = None,
) -> PipelineResult:
    plan = plan_fileops(request, data, on_progress=on_progress)
    if not plan.preflight_manifest.ok:
        return build_preflight_result(plan)
    return _execute_plan(plan, on_progress)
```

### compute() — 改造后

```python
def compute(
    data: dict,              # DataPort.fetch() 返回的 clean dict
    *,
    on_progress: Any = None,
) -> dict:                   # 纯 dict 输出，不碰文件
```

**输入 `data`**：
```python
{
    "database": dict,
    "aggregated_rule_set": dict,
    "branch_decisions": dict | None,
    "managed_entries": dict | None,
}
```

**输出 `dict`**：
```python
{
    "mapping_result": dict,
    "trees": list,
    "errors": list,
    "warnings": list,
    "final_mapping": list,
}
```

> **不负责持久化**——`DataPort.push(dest_desc, intent, PipelineResult)` 将结果写入 workspace（若 `output_type="workspace"`）。

### dispatch() — compute 分支（改造后）

```python
desc = resolver.resolve(request)                    # SourceDescriptor
data = data_port.fetch(desc, request.intent)         # clean dict
result_dict = compute(data, on_progress=on_progress) # 纯 dict
result = PipelineResult(
    ok=not result_dict.get("errors"),
    errors=result_dict.get("errors", []),
    warnings=result_dict.get("warnings", []),
    trees=result_dict.get("trees", []),
    final_mapping=result_dict.get("final_mapping", []),
    mapping_result=result_dict,
)
dest_desc = DestDescriptor(
    output_type=request.output_type,
    workspace_id=request.output_args.get("workspace_id"),
    config_index=request.output_args.get("config_index", ""),
)
data_port.push(dest_desc, request.intent, result)
return result
```

**SPEC 条款（可测试）**

### K1 — kmmignore 遗留代码清理
- [ ] SPEC-K1-01 `planner_fileops.py` 中删除 `_copy_kmmignore_to_backup()` 函数（L209-229）
- [ ] SPEC-K1-02 `planner_fileops.py` 中删除 `_copy_kmmignore_from_backup()` 函数（L232-248）
- [ ] SPEC-K1-03 `orchestrator/__init__.py` 中删除 `_dispatch_fileops` 内 kmmignore copy 调用（L150-155：`if not plan.dry_run: ... _copy_kmmignore_to_backup/copy_kmmignore_from_backup` 整段）
- [ ] SPEC-K1-04 `orchestrator/__init__.py` 顶部 import 中删除 `from .planner_fileops import ... _copy_kmmignore_to_backup, _copy_kmmignore_from_backup`（L27）
- [ ] SPEC-K1-05 代码库中任意 `.py` 文件不再包含 `_copy_kmmignore_to_backup` 或 `_copy_kmmignore_from_backup` 函数定义

### C1 — compute 入口修正

> compute_ws 废除，_dispatch_compute 删除。compute 走 dispatch → resolver → compute 统一路径（与 fileops 对称）。DataPort 和 CleanContext 的最终替换由后续任务卡处理——本次只做路径统一和死代码清退。

- [ ] SPEC-C1-01 删除 `orchestrator/compute_pipeline.py` 中的 `compute_ws()` 函数（L147-234）
- [ ] SPEC-C1-02 `orchestrator/__init__.py` 中删除 `_dispatch_compute()` 函数（L62-74）——该函数绕过 resolver，直接接受 raw dict 入参，与新设计冲突
- [ ] SPEC-C1-03 `dispatch()` 中 `Intent.COMPUTE_MAPPING` 分支改为：选 resolver → resolve → 调 `compute()`（与 fileops 路径对称，均经 resolver）
- [ ] SPEC-C1-04 `orchestrator/__init__.py` 顶部 import 中 `from .compute_pipeline import compute, compute_ws` → 改为 `from .compute_pipeline import compute`（仅保留 `compute`）
- [ ] SPEC-C1-05 Web 路由 `workspace.py` 中 `workspace_compute` 端点（L244-269）：将 `compute_ws(workspace_id=..., config_index=..., ...)` 改为构造 `TaskRequest(identity="web", intent=Intent.COMPUTE_MAPPING, resolver_type="workspace", ...)` 并通过 `dispatch()` 调用
- [ ] SPEC-C1-06 测试 `test_web_api.py` 中 monkey-patch `compute_ws` 的 6 处 fake 函数更新——由 probe 独立按黑箱标准重写（不纳入 smith 实现范围）
- [ ] SPEC-C1-07 `compute_pipeline.py` docstring（L1）删除 `compute_ws` 提及，改为 `"""Compute pipeline — managed filter + compute."""`
- [ ] SPEC-C1-08 `repo_memo/DESIGN_MIGRATION_LAYERS.md` Layer 1 表中 `compute_ws()` 引用删除（若尚未删除）

### D1 — DataPort 实现

> SPEC: `repo_test/dataport_spec.md`（21 条断言）。DataPort 是 orchestrator 唯一 I/O 通道——修复 Resolver 做了 I/O 的问题，为 CleanContext 画句号，同时解决 workspace 写回过渡方案。

- [ ] SPEC-D1-01 新建 `orchestrator/data_port.py`，包含 `SourceDescriptor` dataclass + `fetch()` + `push()` 函数
- [ ] SPEC-D1-02 `SourceDescriptor` 字段（fetch 来源）和 `DestDescriptor` 字段（push 目标）**分开定义**。`push()` 签名为 `push(dest: DestDescriptor, intent, result)`——不使用 SourceDescriptor 混用来源和目标
- [ ] SPEC-D1-03 `TaskRequest` 新增两个字段：
  - `output_type: Literal["workspace", "none"] = "none"` — push 目标类型
  - `output_args: dict[str, Any] = field(default_factory=dict)` — push 目标参数
- [ ] SPEC-D1-04 `fetch(desc: SourceDescriptor, intent)` — 按 source_type + intent 从源头读取数据，返回 clean dicts（见 `PLAN_DATAPORT.md §七`）
- [ ] SPEC-D1-05 `push(dest: DestDescriptor, intent, result)` — 按 `dest.output_type` 决定行为：`"workspace" + COMPUTE_MAPPING` 时写 mapping/SVG/fingerprints 到 workspace；`"none"` 或非 COMPUTE_MAPPING 时无操作
- [ ] SPEC-D1-06 `dispatch()` 中根据 `request.output_type` + `request.output_args` 构建 `DestDescriptor`，传入 `push()`
- [ ] SPEC-D1-07 Resolver 重写为纯解析（无 I/O）：
  - `WorkspaceResolver.resolve()` 返回 `SourceDescriptor(source_type="workspace", workspace_id=..., config_index=...)`，删除 `wm.read_meta/read_mapping/_resolve_database` 等 I/O 调用
  - `FilePathResolver.resolve()` 返回 `SourceDescriptor(source_type="file_paths", database_path=..., config_index=...)`，删除文件读取 I/O
  - `RawDictResolver.resolve()` 返回 `SourceDescriptor(source_type="raw_dict", database_dict=..., aggregated_rule_set=...)`，纯透传
- [ ] SPEC-D1-08 `CleanContext` dataclass 从 `orchestrator/resolver.py` 中**删除**
- [ ] SPEC-D1-09 `plan_fileops()` 签名改为接受 DataPort.fetch() 返回的 dict（而非 CleanContext 对象）——参数从 `context: CleanContext` 改为 `data: dict`，内部 `context.final_mapping` → `data["final_mapping"]` 等
- [ ] SPEC-D1-10 `dispatch()` 流程改为：`Resolver.resolve → DataPort.fetch → Engine/Planner → DataPort.push`
- [ ] SPEC-D1-11 `orchestrator/__init__.py` import 新增 `from .data_port import fetch, push, SourceDescriptor, DestDescriptor`
- [ ] SPEC-D1-12 所有引用 `CleanContext` 的代码更新（测试文件、planner.py 等）。`CleanContext` 类型在整个代码库中不再存在
- [ ] SPEC-D1-13 `database_name` 格式校验：`fetch()` 中校验 name 不含 `..` 等路径穿越字符，不合格时抛异常
- [ ] SPEC-D1-14 Web 路由构造 `TaskRequest` 时显式指定 `output_type="workspace"` + `output_args`（如 `workspace_compute` 端点）

### A1 — preflight 归位
- [ ] SPEC-A1-01 创建目录 `orchestrator/fileops/planner/`
- [ ] SPEC-A1-02 将 `orchestrator/preflight.py` **移动**到 `orchestrator/fileops/planner/preflight.py`（物理移动，保留 git 历史）
- [ ] SPEC-A1-03 preflight.py 内部 import 路径适配：新位置下所有相对 import 需调整（当前 `from ..planner_fileops import check_backup_gate` → `from .planner import check_backup_gate`）
- [ ] SPEC-A1-04 所有引用旧路径 `orchestrator/preflight` 的代码更新为新路径（全局搜索并替换）

### A2 — dispatch_fileops 拆分

> 原则："有哪些事情要交给 planner"归 dispatch；"planner 的任务内容具体是什么"归 fileops。resolver 和 DataPort 均由 orchestrator（dispatch）拉起。

- [ ] SPEC-A2-01 在 `orchestrator/fileops/__init__.py` 中创建 `execute(data, intent, flags, on_progress=None) -> PipelineResult` 函数，吸收当前 `_dispatch_fileops` L111-183 的逻辑：`plan_fileops()` → preflight gate → execute primitive
- [ ] SPEC-A2-02 将当前 `_dispatch_fileops` 的四个内部函数 `_execute_backup_plan`、`_execute_apply_plan`、`_execute_restore_plan`、`_execute_run_plan` 移入 `fileops/__init__.py`
- [ ] SPEC-A2-03 将辅助函数 `_notify` 移入 `fileops/_common.py`
- [ ] SPEC-A2-04 `dispatch()` 中负责"选 resolver + 调 resolve"的逻辑（当前 `_dispatch_fileops` L80-109）**留在 `dispatch()`**，不移入 fileops。dispatch 继续担任 orchestrator 角色——拉 resolver、未来拉 DataPort.fetch、最后调 `fileops.execute()`
- [ ] SPEC-A2-05 `dispatch()` 中 fileops 分支改为：选 resolver → resolve → 调 `fileops.execute(data, intent, flags, on_progress)`
- [ ] SPEC-A2-06 `orchestrator/__init__.py` 删除 `_dispatch_fileops` 及所有 `_execute_*_plan`、`_notify` 函数定义
- [ ] SPEC-A2-07 `orchestrator/__init__.py` 顶部 import 更新：删除不再需要的原语 import，新增 `from .fileops import execute`

### A3 — fileops/ 目录创建
- [ ] SPEC-A3-01 目录结构：
  ```
  orchestrator/fileops/
  ├── __init__.py          ← execute() 统一入口
  ├── _common.py           ← _notify 等共享辅助
  └── planner/
      ├── __init__.py      ← 空或 re-export
      ├── planner.py       ← 当前 planner_fileops.py 移入后重命名
      ├── preflight.py     ← 从 A1 迁入
      └── ignore_rules.py  ← 当前 orchestrator/ignore_rules.py 移入
  ```
- [ ] SPEC-A3-02 将 `orchestrator/planner_fileops.py` **移动**到 `orchestrator/fileops/planner/planner.py`
- [ ] SPEC-A3-03 将 `orchestrator/ignore_rules.py` **移动**到 `orchestrator/fileops/planner/ignore_rules.py`（仅供 Planner 消费）
- [ ] SPEC-A3-04 创建 `orchestrator/fileops/planner/__init__.py`
- [ ] SPEC-A3-05 移动后所有内部 import 路径适配：
  - `planner.py` 中：`from ..resolver import CleanContext` → `from ...resolver import CleanContext`
  - `planner.py` 中：`from .ignore_rules import ...` → `from .ignore_rules import ...`（同级目录不变）
  - `preflight.py` 中：`from ..planner_fileops import check_backup_gate` → `from .planner import check_backup_gate`
  - `ignore_rules.py` 中：若引用外部同级模块需修正路径
- [ ] SPEC-A3-06 所有外部引用更新（全局搜索旧路径）：
  - `orchestrator/__init__.py`：`from .planner_fileops import plan_fileops` → `from .fileops.planner.planner import plan_fileops`
  - `orchestrator/__init__.py`：`from .ignore_rules import` → `from .fileops.planner.ignore_rules import`
  - 其他引用文件同上
- [ ] SPEC-A3-07 原位置不留兼容占位文件

**实现约束**（repo_spec）
- [ ] 使用 `git mv` 移动文件以保留 git 历史
- [ ] 所有内部 import 路径修正（相对 import 层级变动）
- [ ] 所有外部引用路径修正（`orchestrator/__init__.py`、Web 路由、测试文件、文档）
- [ ] 不改变函数签名、不改变错误码、不改变返回值结构
- [ ] `orchestrator/__init__.py` 的 import 最小化——移出原语 import 到 `fileops/__init__.py`，`__init__.py` 只保留 dispatch 路由所需

**验收标准**
- smith: 上述 SPEC-K1/A1/A2/A3 全部条款达成
- probe:
  - 全量测试 `python3 -m pytest tests/` 通过（不含 pre-existing `test_backup_tree.py` 失败）
  - `test_kmmignore_lifecycle.py` 8/8 通过（已更新为黑箱）
  - `test_gate_boundary.py` 通过
  - `test_preflight.py` 通过
  - `test_planner_fileops.py` 通过
  - 无新增 import 错误

**文档落位与收尾**
- 长期结论落位: `repo_memo/DESIGN_PLANNER.md`、`repo_memo/DESIGN_ORCHESTRATOR.md`（已在前期更新）
- 随代码变更需同步更新的文档：
  - `repo_memo/DESIGN_MIGRATION_LAYERS.md`：Layer 1 模块表需更新 `ignore_rules.py` 新路径
  - `compute_pipeline.py` docstring：删除 `compute_ws` 提及
  - `repo_test/gate_boundary.md`、`repo_test/kmmignore_lifecycle.md`：若引用了旧路径需修正
- work_memo 收尾: 任务完成后由 arch 判定归档

**前置假设与疑虑**

### 已裁决

- 疑虑-1 ~~ignore_rules 位置~~ → `fileops/planner/`
- 疑虑-2 ~~_notify 位置~~ → `fileops/_common.py`
- 疑虑-3 ~~compute_ws 去留~~ → 删除，走 dispatch 全链路
- 疑虑-4 ~~CleanContext 废除~~ → D1 条款，`plan_fileops()` 改接 `data: dict`
- 疑虑-5 ~~import 清理~~ → 最小必要原则
- 疑虑-6 ~~文档同步~~ → 已修正
- 疑虑-7 ~~workspace_compute 新流程~~ → `TaskRequest(output_type="workspace")` + `dispatch()`
- 疑虑-8 ~~probe 测试~~ → probe 独立按 SPEC 写黑箱测试
- 疑虑-9 ~~写回过渡方案~~ → DataPort.push(DestDescriptor)
- 疑虑-10 ~~规模~~ → 45 条条款，5 阶段拆分提交

### 接口契约

- 契约-1 ~~plan_fileops 新签名~~ → 见上方"接口契约"节：`plan_fileops(request, data: dict)`，data 含 `database/user_config/final_mapping`
- 契约-2 ~~compute 改造~~ → 方案 A：`compute(data: dict) -> dict`，纯计算不碰文件。DataPort.push 负责持久化
- 契约-3 ~~dict 结构定义~~ → 两种 data dict 结构已在接口契约中显式定义

### 待确认

- 中间态处理：每个阶段只跑该阶段相关的单元测试。smith 自行判断哪些测试属于当前阶段。集成测试在全部完成后统一执行
- probe 边界：probe 不读实现代码——按 SPEC + schema 写黑箱测试。若 SPEC/schema 信息不足，arch 补全后再让 probe 动手
