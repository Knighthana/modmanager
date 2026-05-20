# DESIGN_FOREST_MODEL — 森林模型重构

> Status: stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 compute_mapping 的森林模型、解析流程与 trees/final_mapping 输出契约

> 来源：DESIGN_P0_FOREST_RISK_ANALYSIS.md + DESIGN_P0_FOREST_IMPLEMENTATION.md（合并）
> 实现状态：已落地并持续生效

---

## 一、背景与风险分析（DESIGN_P0_FOREST_RISK_ANALYSIS.md）

### 1. 现状剖析：当前 `compute_mapping` 的数据流

```
aggregated_rule_set (operation[]) ──→ database ──→ branch_decisions (optional)
                   │
    ┌──────────────▼────────────────┐
    │    compute_mapping()          │
    │                              │
    │  1. 展开 actionlist →        │
    │     构建 mapping dict        │
    │     (target → node)         │
    │     edges dict (src→tgts)  │
    │                              │
    │  2. find_cycles(edges)       │
    │                              │
    │  3. 同 mod 去重              │
    │     (later wins)             │
    │                              │
    │  4. 输出 trees (扁平列表)    │
    │     + final_mapping          │
    └──────────────┬───────────────┘
                   │
    { warnings, errors, trees, final_mapping }
```

#### 当前 trees 数据结构

```python
# trees[i] = {
#     "path":              str,      # 目标文件绝对路径
#     "destin_mixed_id":   str,      # 所属 mod 的 mixed_id
#     "changerequest":     [dict],   # 有序的源请求列表
#     "warning":           str|None, # "W_FOREST_BRANCHING" 或 None
#     "candidates":        [str],    # 分岔候选源列表
# }
```

**关键特征**：
- trees 是**扁平列表**，不是图；每个条目是一个"目标文件"
- "分岔"（branching）发生在一个目标有多条 changerequest 时
- changerequest 的 `path` 字段是源文件路径；若该路径恰好也是另一个目标 → 形成链
- 链的解析通过 `_resolve_effective_leaf_request` **自上而下**递归跟踪

#### 当前 delete 的处理路径（问题所在）

```python
# engine.py L381-398: delete 规则
if action == "delete":
    target = _norm(str(Path(dest_root) / _norm(into_target)))
    mapping[target]["changerequest"].append({
        "path": "!",      # 特殊值，"!" 表示删除
        "action": "delete",
        ...
    })
```

然后 `_resolve_effective_leaf_request` 会跟踪链：
- 若目标 T 的 changerequest 源路径是另一个目标 S
- 递归查询 S 的有效叶结点
- 若 S 的有效叶是 delete（path="!"），则 T 的有效叶**被提升为 delete**，触发 `W_DELETE_LEAF_PROMOTED`

**这就是旧模型的核心问题**：delete 语义沿链向上传播（"刨根移栽"），源文件的删除变成了目标文件的删除。

### 2. 新模型的设计要点

#### 核心思想：独立根 + 引用

```
旧模型（刨根移栽）:
  /game/target.png ←── replace ── /modA/file.png ←── delete
                                    ↑
                               delete 效果移植到 target.txt
                               （source 删除 → target 也被删除）

新模型（独立根 + 引用）:
  Tree X: /modA/file.png ──[delete]              ← 独立决策
  Tree Y: /game/target.png                       ← 独立根
            ↑ ref: /modA/file.png                ← 引用，非占有

  Tree X 先决策 → X 被删除
  Tree Y 查询 → ref 已失效 → Tree Y 操作失败（报错/警告）
  （不是把 target 也删了）
```

#### 数据结构：ForestTree

```python
@dataclass
class ForestTree:
    root_path: str                  # 树的根路径（一个文件）
    operations: list[ChangeRequest] # 对这棵树根的操作列表
    refs: list[str]                 # 引用了哪些其他树的根
    resolved: bool                  # 是否已解析
    resolved_state: str | None      # "deleted" | "kept" | None
```

#### 解析算法：从底向上

```
拓扑排序（被引用者先于引用者）→ 从底向上逐层解析：
  Step 1: 查询所有被引用树的状态
  Step 2: 若有自己的操作 + 源均可用 → 用户在此决策
  Step 3: 标记为已解析
```

### 3. 关键架构判断：重构 vs 修改

| 维度 | 纯重构（内部不变） | 新模型（公开接口变） |
|------|-------------------|---------------------|
| `compute_mapping` 内部逻辑 | 小改 | **大改**（解析算法重写） |
| 输出 `trees` 结构 | 不变 | 可能增加字段 |
| 输出 `final_mapping` 结构 | 不变 | 结构不变，语义可能变 |
| `branch_decisions` 输入 | 不变 | **格式改变** |
| 下游 orchestrator | 不变 | 可能需要适配 |
| 下游 forest_visual.py | 不变 | **大幅修改**（概念从 target 变为 tree） |

**结论**：这是一个**模型演进**，不是纯重构。

### 4. 爆炸半径分析

| 模块 | 文件 | 改动量评估 | 风险等级 |
|------|------|-----------|---------|
| **引擎核心** | `engine.py` | **重写** `_resolve_effective_leaf_request` 及相关逻辑（约150行）；新增 ~200+行 | 🔴 高 |
| **编排层** | `orchestrator/` | 小改（`PipelineResult` 字段更名） | 🟡 中 |
| **可视化** | `forest_visual.py` | **重写** 核心模型 + 新增 ref 边渲染 | 🔴 高 |
| **Web API** | `schemas.py` / `adapters.py` / `routes/` | 适配新字段 | 🟡 中 |
| **前端** | `types/` / `stores/` / `pages/` / `components/` | 冲突裁决模型重写 | 🔴 高 |

### 5. 风险清单

**🔴 高风险**
| # | 风险 | 缓解措施 |
|---|------|---------|
| R1 | delete 语义兼容性 — 新模型不再"刨根移栽" | 明确定义新旧语义差异，审查测试中的 delete 场景 |
| R2 | 前端冲突裁决大改 — 从"按目标选源"变为"按树决策" | 前后端同步设计，先定接口契约再分别实现 |
| R3 | branch_decisions 格式断裂 | 使用不同的 key 命名或版本化 |
| R4 | forest_visual 渲染重写 | 复用部分 DOT/SVG 生成逻辑 |

**🟡 中风险**
| # | 风险 | 缓解措施 |
|---|------|---------|
| R5 | 拓扑排序正确性 — 树间引用可能形成复杂 DAG | 复用 `find_cycles()`；新增独立树级拓扑排序 |
| R6 | 用户决策反馈到 final_mapping 的状态机 | 明确定义决策→final_mapping 的状态传播 |
| R7 | ForestTree 构建逻辑 — 从 mapping+edges 提取 | 在 engine.py 构建循环中增加提取步骤 |

### 6. 决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | 激进程度 | **激进** — 全栈一次性切换，不接受技术债 |
| D2 | delete 源失效行为 | **跳过 + warning** — 不报错，不传播 |
| D3 | T5（目录 delete 裂变） | **不实现** — 改用"祖先路径前缀检查" |
| D4 | `branch_decisions` 格式 | **向后兼容扩展** — 增加 `"!"` / `""` 语义 |

---

## 二、详细实现方案（DESIGN_P0_FOREST_IMPLEMENTATION.md）

### 1. 新数据结构定义

#### 1.1 `ForestTree`（引擎内部数据结构）

```python
@dataclass
class ForestTree:
    """一棵独立根树。每棵树代表一个文件路径的操作集合。"""
    root_path: str                     # 树的根路径（＝该文件在文件系统中的路径）
    destin_mixed_id: str               # 所属 mod 的 mixed_id（来自首个 changerequest）
    changerequest: list[dict]          # 对这个根的所有操作（跨 mod 的竞争操作）
    refs: list[str]                    # 引用了哪些其他树的根路径
    resolved: bool = False             # 是否已完成解析
    # resolved_state 由引擎内部驱动，不暴露给外部：
    #   None          — 尚未解析
    #   "kept"        — 源可用，保留在 final_mapping
    #   "deleted"     — 根路径被删除（标记为不可用作源）
    #   "failed"      — 所有操作源都失效
    #   "skipped"     — 用户决策跳过
```

#### 1.2 `trees` 输出格式

`compute_mapping` 输出中的 `"trees"` key，列表元素结构：

```python
# trees[i] = {
#     "root_path":         str,       # 树的根路径
#     "destin_mixed_id":   str,       # mod 标识
#     "changerequest":    [dict],     # 操作列表
#     "refs":             [str],      # 引用的其他根路径
#     "resolved_state":   str,        # "pending" | "kept" | "deleted" | "failed" | "skipped"
#     "warning":           str|None,  # 树的警告（如 "W_FOREST_BRANCHING"）
#     "candidates":        [str],     # 分岔候选（仅 resolved_state="pending" 时存在）
# }
```

#### 1.3 `final_mapping` 格式（保持不变）

```python
# final_mapping[i] = {
#     "path":    str,       # 目标文件路径
#     "request": {
#         "path":  str,     # 源文件路径（"!" 表示 delete）
#         "action": str,    # "replace" | "create" | "delete"
#         ...
#     }
# }
```

**关键不变**：`backup_ops` 消费 `final_mapping` 的契约保持不变，无需改动 backup 模块。

#### 1.4 `branch_decisions` 格式（向后兼容扩展）

```python
# branch_decisions = {
#     "<tree_root_path>": "<decision_value>"
# }
# 
# decision_value 的含义：
#   "/abs/path/to/source"  → 为该树选择此源路径（replace/create 操作）
#   "!"                    → 接受 delete 操作
#   ""                     → 跳过该树（keep as-is，不执行任何操作）
#   not present            → 自动裁决（单操作树）/ 报错（多操作树）
```

### 2. `compute_mapping` 改造方案

#### 2.1 变更总览

| 当前区域 | 改动性质 | 说明 |
|---------|---------|------|
| `compute_mapping()` 下半段 | **重写** | 构建 trees 和 final_mapping 的逻辑替换 |
| `_resolve_effective_leaf_request()` | **完全移除** | 旧的自顶向下递归替换为自底向上树解析 |
| `_sort_request_key()` | 保留 | 同 mod 去重逻辑不变 |
| `_pick_request_by_action_order()` | **移至树解析** | 在树解析阶段调用 |
| 新增 `_build_forest_trees()` | **新增** | 从 mapping dict + edges dict 构建 ForestTree 列表 |
| 新增 `_resolve_trees_bottom_up()` | **新增** | 拓扑排序 + 自底向上解析 |
| 新增 `_ancestor_deleted()` | **新增** | 路径前缀检查（T5 替代方案） |

#### 2.2 新流程图

```
compute_mapping(aggregated_rule_set, database, branch_decisions)
  │
  ├─ 1. 输入校验 (不变) ─────────────────────────────────────
  │     validate_aggregated_rule_set / validate_database / validate_branch_decisions_schema
  │
  ├─ 2. 展开 actionlist → 构建 mapping dict + edges dict (不变) ──
  │
  ├─ 3. 成环检测 + 同 mod 去重 (不变) ────────────────────────
  │     find_cycles(edges) + same-mod dedup
  │
  ├─ 4. ── 新 ── 构建 ForestTree 列表 ────────────────────────
  │     _build_forest_trees(mapping, edges, mod_index)
  │     → 每个 mapping 的 key 为一棵树的 root_path
  │     → 从 changerequest 提取 refs
  │     → 返回 list[ForestTree]
  │
  ├─ 5. ── 新 ── 拓扑排序 ───────────────────────────────────
  │     topological_sort_by_refs(trees)
  │     → 被引用者先于引用者
  │     → 环检测：复用 find_cycles(ref_graph)
  │
  ├─ 6. ── 新 ── 从底向上解析 ──────────────────────────────
  │     _resolve_trees_bottom_up(sorted_trees, branch_decisions)
  │     对每棵树（按拓扑序）：
  │       a. 收集自身操作
  │       b. 对每个 ref_path，查找被引用树的状态
  │       c. 剔除源失效的操作
  │       d. 应用 branch_decisions
  │       e. 裁决
  │
  ├─ 7. ── 新 ── 祖先检查（T5 替代） ────────────────────────
  │     对每个非 delete 树，检查其源路径是否以任何 deleted 树为前缀
  │
  ├─ 8. 构建输出 ─────────────────────────────────────────────
  │     trees 列表 + final_mapping 列表
  │
  └─ 9. 返回 {warnings, errors, trees, final_mapping}
```

#### 2.3 关键函数设计

**`_build_forest_trees`**：从 mapping dict 中为每个 target 构建一棵 ForestTree，识别 refs（源路径也在 mapping 中的情况）。

**`_topological_sort_by_refs`**：按引用关系拓扑排序，被引用者先于引用者。检测成环。

**`_resolve_trees_bottom_up`**：核心解析函数。对每棵树按拓扑序解析：
1. 收集有效操作（排除源失效的操作）
2. 应用用户决策（branch_decisions）
3. 自动裁决：0 操作→failed，1 操作→auto-resolve，多操作→pending

**`_any_ancestor_deleted`**：检查路径的任一祖先目录是否对应已删除的树（T5 替代方案）。

#### 2.4 构建最终输出

```python
def _build_output(trees, warnings, errors) -> dict:
    # 检查未决议的分岔
    # 构建 trees 输出（含 candidates/warning）
    # 构建 final_mapping（仅 kept/deleted 状态）
    # 若 errors 非空 → final_mapping 清空
```

### 3. 下游模块适配

| 模块 | 改动内容 |
|------|---------|
| `orchestrator/` | `PipelineResult.trees` |
| `modmanager_web/schemas.py` | `trees: list[dict]` |
| `modmanager_web/adapters.py` | key 使用 `trees` |
| `forest_visual.py` | 重写 `_build_graph_model()`，以"树"为中心 |
| 前端 TypeScript | `TreeNode` 类型更新 |
| 前端 stores | `trees` 状态管理 |
| 前端 ConflictsPage | 冲突展示改为"按树裁决" |

### 4. 任务分解与执行顺序

```
Step 1: 引擎核心新函数（纯逻辑，不破坏现有代码）
  Task P0-01 ~ P0-06: ForestTree dataclass + 5 个新函数

Step 2: 引擎核心测试
  Task P0-07 ~ P0-10: 新函数单元测试

Step 3: 重构 compute_mapping() 主函数
  Task P0-11 ~ P0-13: 重写下半段 + 移除旧函数

Step 4: 集成测试适配
  Task P0-14 ~ P0-16: 更新 engine/contract/fixtures 测试

Step 5: 下游模块适配
  Task P0-17 ~ P0-19: orchestrator + Web API + 测试

Step 6: forest_visual.py 重写
  Task P0-20 ~ P0-25: 以树为中心的渲染

Step 7: 前端适配
  Task P0-26 ~ P0-30: types/stores/pages/components + 测试

Step 8: 全量回归
  Task P0-31 ~ P0-33: Python 全量 + 前端构建 + E2E
```

### 5. 验收标准

1. **输出**：含 `"trees"` key（数组），不含 `"forest"` key
2. **delete 语义**：限于自身树根，不向上传播；引用已 delete 树 → 跳过（warning）
3. **分岔裁决**：多操作树 → `resolved_state="pending"`；用户决策后 → `"kept"` / `"deleted"`
4. **下游不改崩**：`backup_ops` 零改动；orchestrator 仅字段更名
5. **全量测试通过**：Python + 前端

### 6. 术语规范

| 中文 | 含义 | 代码中 |
|------|------|--------|
| **树** | ForestTree 实例 | `tree` |
| **根** | 树的根路径 | `root_path` |
| **结点** | 可视化图上的元素 | `node` |
| **分枝** | 多操作待决策 | `pending` / `branching` |
| **引用** | 树之间的依赖边 | `ref` / `refs` |
