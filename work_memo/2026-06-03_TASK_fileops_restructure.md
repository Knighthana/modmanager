## Task-Card: fileops 目录重构 + kmmignore 代码清理

**目标**
完成 `orchestrator/` 下 fileops 目录结构创建、Planner 入口统一、preflight 归位、kmmignore 遗留代码删除。不改变任何外部行为。

**L1 硬约束**
- [ ] L1-1 本次仅做目录/文件重组 + 死代码删除，**不改变任何运行时行为**
- [ ] L1-2 所有现有测试必须通过（不含 pre-existing `test_backup_tree.py` 失败）
- [ ] L1-3 原语之间互不知晓，不感知 `.kmmignore` / gate 逻辑

**SPEC 条款（可测试）**

### K1 — kmmignore 遗留代码清理
- [ ] SPEC-K1-01 `planner_fileops.py` 中删除 `_copy_kmmignore_to_backup()` 函数（L209-229）
- [ ] SPEC-K1-02 `planner_fileops.py` 中删除 `_copy_kmmignore_from_backup()` 函数（L232-248）
- [ ] SPEC-K1-03 `orchestrator/__init__.py` 中删除 `_dispatch_fileops` 内 kmmignore copy 调用（L150-155：`if not plan.dry_run: ... _copy_kmmignore_to_backup/copy_kmmignore_from_backup` 整段）
- [ ] SPEC-K1-04 `orchestrator/__init__.py` 顶部 import 中删除 `from .planner_fileops import ... _copy_kmmignore_to_backup, _copy_kmmignore_from_backup`（L27）
- [ ] SPEC-K1-05 代码库中任意 `.py` 文件不再包含 `_copy_kmmignore_to_backup` 或 `_copy_kmmignore_from_backup` 函数定义

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
- [ ] 所有外部引用路径修正（`orchestrator/__init__.py`、Web 路由、测试文件）
- [ ] 不改变函数签名、不改变错误码、不改变返回值结构

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
- 长期结论落位: `repo_memo/DESIGN_PLANNER.md`、`repo_memo/DESIGN_ORCHESTRATOR.md`（已更新）
- work_memo 收尾: 任务完成后由 arch 判定归档

**前置假设与疑虑**

- 假设：`planner_fileops.py` 中除 `_copy_kmmignore_*` 外无其他死代码
- 假设：`git mv` + import 修正后 Python 能正常加载模块（无循环导入）
- 疑虑-1：`ignore_rules.py` 被 Planner 独享，移入 `fileops/planner/` 合理。但若未来有非 Planner 模块也想用它（如 CLI 直接调用），则放 `orchestrator/` 根目录更合适。当前确认移入？
- 疑虑-2：`_notify` 辅助函数——放入 `fileops/_common.py` 还是保留在 `_common.py`？它是 fileops 专属（进度通知），放 `fileops/_common.py` 更干净
- 疑虑-3：`_dispatch_compute` 函数仍留在 `orchestrator/__init__.py`——不在此次范围，compute 全链路改造由后续 DataPort 任务卡处理
- 疑虑-4：`orchestrator/__init__.py` 的 import 中有 `from .compute_pipeline import compute, compute_ws`——`compute_ws` 尚未删除（代码仍存在），本次不动它。compute 清除由后续任务卡处理
- 疑虑-5：`CleanContext` 未在本次任务中废除——仍在 `resolver.py` 和 `planner.py` 中使用。由后续 DataPort 任务卡处理
