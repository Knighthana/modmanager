# P0：森林模型重构 — 详细实现方案设计

创建：2026-05-06
状态：已完成 ✅
来源：`work_memo/FOREST_DELETE_FORK_DESIGN.md` §7-13
前置分析：`repo_memory/direct/DESIGN_P0_FOREST_RISK_ANALYSIS.md`

---

## 0. 决策确认

| # | 决策 | 结论 |
|---|------|------|
| D1 | 激进程度 | **激进** — 全栈一次性切换，不接受技术债。旧 `forest` 格式移除，替换为 `trees` 格式 |
| D2 | delete 源失效行为 | **跳过 + warning** — 引用树的源被 delete 后，引用者操作跳过，不报错 |
| D3 | T5 (目录 delete 裂变) | **不实现** — 改用"祖先路径前缀检查"判断源是否在 deleted 目录下 |
| D4 | `branch_decisions` 格式 | **向后兼容扩展** — 基础格式不变（`{root: source_path}`），增加 `"!"` 表示接受 delete，`""` 表示跳过 |

---

## 1. 新数据结构定义

### 1.1 `ForestTree`（引擎内部数据结构）

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

### 1.2 `trees` 输出格式（替代旧 `forest`）

`compute_mapping` 输出中的 `"forest"` key 改为 `"trees"`，列表元素结构：

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

### 1.3 `final_mapping` 格式（保持不变）

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

### 1.4 `branch_decisions` 格式（向后兼容扩展）

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

---

## 2. `compute_mapping` 改造方案

### 2.1 变更总览

| 当前行号/函数 | 改动性质 | 说明 |
|-------------|---------|------|
| L290-534 `compute_mapping()` | **重写下半段** | 构建 forest 和 final_mapping 的逻辑替换 |
| L114-149 `_resolve_effective_leaf_request()` | **完全移除** | 旧的自顶向下递归替换为自底向上树解析 |
| L71-76 `_sort_request_key()` | 保留 | 同 mod 去重逻辑不变 |
| L79-111 `_pick_request_by_action_order()` | **移至树解析** | 在树解析阶段调用 |
| 新增 `_build_forest_trees()` | **新增** | 从 mapping dict + edges dict 构建 ForestTree 列表 |
| 新增 `_resolve_trees_bottom_up()` | **新增** | 拓扑排序 + 自底向上解析 |
| 新增 `_ancestor_deleted()` | **新增** | 路径前缀检查（T5 替代方案） |

### 2.2 新流程图

```
compute_mapping(aggregated_rule_set, database, branch_decisions)
  │
  ├─ 1. 输入校验 (不变) ─────────────────────────────────────
  │     validate_aggregated_rule_set / validate_database / validate_branch_decisions_schema
  │
  ├─ 2. 展开 actionlist → 构建 mapping dict + edges dict (不变) ──
  │     L332-447 保留
  │
  ├─ 3. 成环检测 + 同 mod 去重 (不变) ────────────────────────
  │     find_cycles(edges) + same-mod dedup
  │
  ├─ 4. ── 新 ── 构建 ForestTree 列表 ────────────────────────
  │     _build_forest_trees(mapping, edges, mod_index)
  │     → 每个 mapping 的 key 为一棵树的 root_path
  │     → 从 changerequest 提取 refs（cr.path 若在 mapping 中 → 是引用）
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
  │          - 若 resolved_state="deleted" → 标记该操作源失效
  │       c. 剔除源失效的操作
  │       d. 应用 branch_decisions 中对该树的用户决策
  │       e. 裁决：
  │          - 0 个有效操作 → resolved_state="failed" + warning
  │          - 1 个有效操作（非 delete） → auto-resolve → resolved_state="kept"
  │          - 1 个有效操作（delete） → 若 branch_decisions[root]="!" 则接受删除 → resolved_state="deleted"
  │                                    → 若未指定 → 自动接受删除 → resolved_state="deleted"
  │          - >1 个有效操作 → 若 branch_decisions 指定则选 → resolved_state="kept"
  │                           → 否则标记为 pending（或错误，视策略）
  │
  ├─ 7. ── 新 ── 祖先检查（T5 替代） ────────────────────────
  │     对每个 delete 树，检查其 resolved_state="deleted"
  │     对每个非 delete 树，检查其源路径是否以任何 deleted 树为前缀
  │     → 若匹配 → 源也标记为失效 → 回到步骤 6 重新裁决
  │
  ├─ 8. 构建输出 ─────────────────────────────────────────────
  │     trees 列表：每个 ForestTree 转 dict
  │     final_mapping 列表：trees 中 resolved_state="kept" 或 "deleted" 的条目
  │
  └─ 9. 返回 {warnings, errors, trees, final_mapping}
```

### 2.3 关键函数伪代码

#### `_build_forest_trees`

```python
def _build_forest_trees(
    mapping: dict[str, dict],
    edges: dict[str, set[str]],
) -> list[ForestTree]:
    trees: list[ForestTree] = []
    for target_path, node in sorted(mapping.items()):
        requests = node["changerequest"]
        destin = node.get("destin_mixed_id", "")
        refs: list[str] = []
        for cr in requests:
            src = cr.get("path", "")
            # 若源路径也是 mapping 中的 key → 引用边
            if src and src != "!" and src in mapping:
                refs.append(src)
        # 去重 refs
        refs = sorted(set(refs))
        trees.append(ForestTree(
            root_path=target_path,
            destin_mixed_id=destin,
            changerequest=requests,
            refs=refs,
        ))
    return trees
```

#### `_topological_sort_by_refs`

```python
def _topological_sort_by_refs(trees: list[ForestTree]) -> list[ForestTree]:
    """按引用关系拓扑排序：被引用者先于引用者。检测成环。"""
    ref_graph: dict[str, set[str]] = {
        t.root_path: set(t.refs) for t in trees
    }
    cycles = find_cycles(ref_graph)
    if cycles:
        # 环内所有树合并为一个决策单元
        return _merge_cycles_and_sort(trees, cycles)
    # Kahn 算法
    ...
```

#### `_resolve_trees_bottom_up`

```python
def _resolve_trees_bottom_up(
    trees: list[ForestTree],
    branch_decisions: dict[str, str],
    warnings: list[str],
    errors: list[str],
) -> None:
    """原地修改 trees，填充 resolved_state。"""
    # 构建快速查找
    tree_by_root: dict[str, ForestTree] = {t.root_path: t for t in trees}
    
    for tree in trees:
        if tree.resolved:
            continue
        
        # ── 收集有效操作 ──
        valid_requests: list[dict] = []
        for cr in tree.changerequest:
            src_path = cr.get("path", "")
            action = cr.get("action", "")
            
            # delete 操作永远有效（源是 "!"，不受其他树影响）
            if action == "delete":
                valid_requests.append(cr)
                continue
            
            # 非 delete 操作：检查源是否存在
            if src_path in tree_by_root:
                ref_tree = tree_by_root[src_path]
                if ref_tree.resolved_state == "deleted":
                    warnings.append(f"W_SOURCE_DELETED: {tree.root_path}: source {src_path} was deleted")
                    continue  # 源被删除，此操作无效
                if ref_tree.resolved_state == "failed":
                    continue  # 源的树失败，此操作也无效
            # 源路径不是任何树的根 → 检查是否在某个 deleted 树的路径下（祖先检查）
            elif _any_ancestor_deleted(src_path, tree_by_root):
                warnings.append(f"W_SOURCE_DIRECTORY_DELETED: {src_path} (ancestor deleted)")
                continue
            
            valid_requests.append(cr)
        
        # ── 应用用户决策 ──
        user_decision = branch_decisions.get(tree.root_path)
        if user_decision is not None:
            if user_decision == "":
                tree.resolved_state = "skipped"
                tree.resolved = True
                continue
            if user_decision == "!":
                # 用户确认删除
                tree.resolved_state = "deleted"
                tree.resolved = True
                continue
            # 用户选了特定源路径
            chosen = next((cr for cr in valid_requests if cr.get("path") == user_decision), None)
            if chosen:
                valid_requests = [chosen]
            else:
                errors.append(f"E_BRANCH_DECISION_INVALID: {tree.root_path}: source {user_decision} not available")
                tree.resolved_state = "failed"
                tree.resolved = True
                continue
        
        # ── 裁决 ──
        if not valid_requests:
            tree.resolved_state = "failed"
            warnings.append(f"W_NO_VALID_OPERATION: {tree.root_path}: all sources unavailable")
        elif len(valid_requests) == 1:
            req = valid_requests[0]
            if req.get("action") == "delete":
                tree.resolved_state = "deleted"
            else:
                tree.resolved_state = "kept"
        else:
            # 多操作：若 branch_decisions 未覆盖 → 标记为 pending
            if tree.root_path in branch_decisions:
                chosen = next((cr for cr in valid_requests if cr.get("path") == branch_decisions[tree.root_path]), None)
                if chosen:
                    tree.resolved_state = "kept" if chosen.get("action") != "delete" else "deleted"
                else:
                    tree.resolved_state = "failed"
            else:
                tree.resolved_state = "pending"  # 等待用户决策
                warnings.append(f"W_FOREST_BRANCHING: {tree.root_path}")
        
        tree.resolved = True
```

#### `_any_ancestor_deleted`

```python
def _any_ancestor_deleted(path: str, tree_by_root: dict[str, ForestTree]) -> bool:
    """检查 *path* 的任一祖先目录是否对应一棵已删除的树。"""
    from pathlib import PurePosixPath
    p = PurePosixPath(path)
    # 沿路径向上检查每个祖先目录
    for ancestor in p.parents:
        ancestor_str = str(ancestor)
        if ancestor_str in tree_by_root:
            if tree_by_root[ancestor_str].resolved_state == "deleted":
                return True
    return False
```

### 2.4 构建最终输出

```python
def _build_output(trees: list[ForestTree], warnings: list[str], errors: list[str]) -> dict:
    """从解析后的 trees 构建最终输出。"""
    
    # ── 检查是否有未决议的分岔 ──
    pending_trees = [t for t in trees if t.resolved_state == "pending"]
    if pending_trees:
        for t in pending_trees:
            warnings.append(f"W_FOREST_BRANCHING_UNRESOLVED: {t.root_path}")
    
    # ── 构建 trees 输出 ──
    trees_output: list[dict] = []
    for tree in trees:
        entry: dict = {
            "root_path": tree.root_path,
            "destin_mixed_id": tree.destin_mixed_id,
            "changerequest": tree.changerequest,
            "refs": tree.refs,
            "resolved_state": tree.resolved_state,
        }
        if tree.resolved_state == "pending":
            entry["warning"] = "W_FOREST_BRANCHING"
            entry["candidates"] = [cr.get("path", "") for cr in tree.changerequest]
        trees_output.append(entry)
    
    # ── 构建 final_mapping ──
    final_mapping: list[dict] = []
    for tree in trees:
        if tree.resolved_state in ("kept", "deleted"):
            # 找到生效的 changerequest
            if tree.resolved_state == "deleted":
                effective_request = {"path": "!", "action": "delete", "hashtype": "sha256", "hashvalue": "0"}
            else:
                # kept: 从有效操作中找（单操作树的唯一操作）
                effective_request = tree.changerequest[0]  # 已被裁决为单操作
            final_mapping.append({
                "path": tree.root_path,
                "request": effective_request,
            })
    
    if errors:
        final_mapping = []
    
    return {
        "warnings": warnings,
        "errors": errors,
        "trees": trees_output,
        "final_mapping": final_mapping,
    }
```

---

## 3. 下游模块适配方案

### 3.1 `orchestrator.py`

| 位置 | 改动 |
|------|------|
| `PipelineResult.forest` 字段 | 改为 `PipelineResult.trees` |
| `compute()` L141 | `forest=...` → `trees=...` |
| `run()` 中的引用 | `compute_result.forest` → `compute_result.trees` |
| 其他 | `mapping_result` dict 中读取 key 从 `"forest"` 变为 `"trees"` |

### 3.2 `modmanager_web/schemas.py`

| 位置 | 改动 |
|------|------|
| `ApiResponse.data` | 无改动（dict 动态） |
| `VisualizeRequest` L97 | `forest: list[dict]` → `trees: list[dict]`，增加 `mapping_result` 的默认 fallback |

### 3.3 `modmanager_web/adapters.py`

| 函数 | 改动 |
|------|------|
| `adapt_pipeline_result()` | `"forest": pr.forest` → `"trees": pr.trees` |

### 3.4 `modmanager_web/routes/pipeline.py`

| 端点 | 改动 |
|------|------|
| `POST /api/pipeline/visualize` | 输入 field 从 `forest` 改为 `trees` |

### 3.5 `forest_visual.py`（重写核心）

当前 `_build_graph_model()` 以 **target 结点**为中心。

新设计以 **树**为中心：
- 结点：每棵树的根路径（target 类型）——为其自身
- 源结点：changerequest 中的源路径（若不是另一棵树的根，则是外部源）
- 边：
  - **操作边**：源 → 树根（标注 action、mixed_id）
  - **引用边**：树根 → 被引用的树根（虚线，标注 "ref"）
- 分岔标记：`resolved_state="pending"` 的树 → 红色高亮

```python
@dataclass
class TreeGraphNode:
    tree_id: str              # root_path
    resolved_state: str       # "pending" | "kept" | "deleted" | "failed" | "skipped"
    destin_mixed_id: str
    warning: str
    candidates: list[str]

@dataclass
class TreeGraphEdge:
    source_path: str
    target_path: str
    edge_type: str            # "operation" | "reference"
    action: str
    mixed_id: str
```

改动量估计：
- `_build_graph_model()` → `_build_tree_graph_model()`：约 80 行重写
- `_render_ascii()`：约 40 行改写（显示树层结构和引用）
- `_render_dot()`：约 60 行改写（新增引用边样式）
- `_enrich_svg_nodes()`：约 20 行改写（data 属性从 forest-node 变为 tree-node）
- `_render_html()`：约 100 行重写（JavaScript 部分的树布局逻辑）

### 3.6 前端

#### `types/index.ts`

```typescript
// 旧：ForestNode
// 新：TreeNode
export interface TreeNode {
  root_path: string
  destin_mixed_id: string
  changerequest: Changerequest[]
  refs: string[]
  resolved_state: "pending" | "kept" | "deleted" | "failed" | "skipped"
  warning?: string
  candidates?: string[]
}

export interface ConflictItem {
  root_path: string                // 旧: target
  destin_mixed_id: string
  options: ConflictOption[]        // 旧: candidates (string[])
}

export interface ConflictOption {
  source_path: string              // "/path/to/source" | "!" (delete) | "" (keep)
  action: string
  label: string                    // 前端展示用
}

// branch_decisions 格式不变（Record<string, string>），语义更新
```

#### `stores/forest.ts`

- `forest: ref<ForestNode[]>` → `trees: ref<TreeNode[]>`
- `conflictList: ref<ConflictItem[]>` → 从 `trees` 中过滤 `resolved_state="pending"` 的树
- `branchDecisions` 格式不变，值语义更新（`"!"` = delete, `""` = keep）
- `setDecision(root_path, option_value)` 不变

#### `pages/ConflictsPage.vue`

- 表格列从 target + candidates 改为 root_path + options（含 action 标签）
- 每个冲突树展示其操作选项：
  - "删除此文件" (delete) → value="!"
  - "保留此文件(跳过)" (keep) → value=""
  - "替换为 /path/to/source" (replace) → value="/path/to/source"

#### `components/ForestViewer.vue`

- SVG 结点从 `data-forest-node` 改为 `data-tree-node`
- 冲突结点从 `data-conflict` 改为 `data-tree-pending`
- 新增引用边的渲染（虚线）

---

## 4. 测试迁移策略

### 4.1 测试文件改动矩阵

| 测试文件 | 受影响程度 | 策略 |
|----------|-----------|------|
| `test_engine.py` (759行) | **~20 个用例** | 重写涉及 delete 传播、分岔裁决的测试；新增 ForestTree 构建/解析的单元测试 |
| `test_contract.py` (321行) | **~5 个用例** | `"forest"` → `"trees"` key 变更；新增 `resolved_state`/`refs` 字段断言 |
| `test_integration_fixtures.py` (786行) | **~10 个用例** | F004（成环）/ F006（分岔）/ F007（决策）场景适配新语义 |
| `test_forest_visual.py` (229行) | **~8 个用例** | 图表模型从 target 变为 tree；输入 key 变更 |
| `test_orchestrator.py` (139行) | **~3 个用例** | `PipelineResult.forest` → `trees` |
| `test_web_api.py` (463行) | **~5 个用例** | `forest` key → `trees` key |
| 前端 Vitest (14个) | **~5-8 个** | store/类型/组件测试更新 |

### 4.2 测试策略

**原则**：每个改动模块先补测试，再改实现。

```
阶段 1: Python 单元测试
  ├─ _build_forest_trees 单元测试（纯函数，易于测试）
  ├─ _topological_sort_by_refs 单元测试
  ├─ _any_ancestor_deleted 单元测试
  └─ _resolve_trees_bottom_up 单元测试（用 mock trees）

阶段 2: 集成测试适配
  ├─ 更新 test_engine.py 中受影响的测试
  ├─ 更新 test_contract.py 中的契约测试
  └─ 更新 test_integration_fixtures.py 中的场景测试

阶段 3: 下游模块适配测试
  ├─ test_forest_visual.py
  ├─ test_orchestrator.py
  └─ test_web_api.py

阶段 4: 前端测试
  └─ Vitest 单元测试更新
```

---

## 5. 任务分解与执行顺序

```
┌─────────────────────────────────────────────────────────────┐
│  Phase P0: 森林模型重构（激进全栈）                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1: 引擎核心新函数（纯逻辑，不破坏现有代码）               │
│    Task P0-01: 在 engine.py 中新增 ForestTree dataclass        │
│    Task P0-02: 实现 _build_forest_trees()                     │
│    Task P0-03: 实现 _topological_sort_by_refs()               │
│    Task P0-04: 实现 _ancestor_deleted()                      │
│    Task P0-05: 实现 _resolve_trees_bottom_up()                │
│    Task P0-06: 实现 _build_output()                          │
│                                                             │
│  Step 2: 引擎核心测试（新函数单元测试）                           │
│    Task P0-07: test_engine.py 新增：ForestTree 构建测试         │
│    Task P0-08: test_engine.py 新增：拓扑排序测试                 │
│    Task P0-09: test_engine.py 新增：祖先检查测试                 │
│    Task P0-10: test_engine.py 新增：自底向上解析测试             │
│                                                             │
│  Step 3: 重构 compute_mapping() 主函数                          │
│    Task P0-11: 重写 compute_mapping() 下半段                    │
│                (L450-534 替换，L290-449 保留)                    │
│    Task P0-12: 移除 _resolve_effective_leaf_request()            │
│    Task P0-13: 移除 W_DELETE_LEAF_PROMOTED 相关逻辑              │
│                                                             │
│  Step 4: 集成测试适配                                              │
│    Task P0-14: 更新 test_engine.py（分岔裁决/delete 传播测试）    │
│    Task P0-15: 更新 test_contract.py（forest→trees key）          │
│    Task P0-16: 更新 test_integration_fixtures.py                  │
│                                                             │
│  Step 5: 下游模块适配                                              │
│    Task P0-17: orchestrator.py PipelineResult forest→trees    │
│    Task P0-18: modmanager_web schemas/adapters/routes 适配      │
│    Task P0-19: 更新下游模块测试                                    │
│                                                             │
│  Step 6: forest_visual.py 重写                                       │
│    Task P0-20: 重写 _build_tree_graph_model()                 │
│    Task P0-21: 重写 _render_ascii()（树层结构+引用）             │
│    Task P0-22: 重写 _render_dot()（新增引用边样式）              │
│    Task P0-23: 更新 _enrich_svg_nodes()（tree-node 属性）      │
│    Task P0-24: 更新 _render_html()（JS 部分）                 │
│    Task P0-25: 更新 test_forest_visual.py                          │
│                                                             │
│  Step 7: 前端适配                                                   │
│    Task P0-26: 更新 types/index.ts（TreeNode/ConflictOption）│
│    Task P0-27: 更新 stores/forest.ts（trees 状态管理）        │
│    Task P0-28: 更新 ConflictsPage.vue（新冲突展示模型）       │
│    Task P0-29: 更新 ForestViewer.vue（tree-node 属性）        │
│    Task P0-30: 前端 Vitest 测试更新                              │
│                                                             │
│  Step 8: 全量回归                                                │
│    Task P0-31: Python 全量测试 280 → 确保通过                  │
│    Task P0-32: 前端构建 + Vitest 全量通过                       │
│    Task P0-33: 手动 E2E 验证（Forest 页面 + 冲突裁决流程）       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. 与现有 demo 聚合器的关系

`cli-hmi/rule_aggregator.py` 是 demo 用途的独立脚本，不消费 `compute_mapping` 输出，无需改动。

---

## 7. 验收标准

1. **`compute_mapping` 输出**：
   - 输出包含 `"trees"` key（数组），不含 `"forest"` key
   - `trees[i]` 包含 `root_path`、`destin_mixed_id`、`changerequest`、`refs`、`resolved_state`
   - `final_mapping` 格式不变
   - 不再出现 `W_DELETE_LEAF_PROMOTED` 警告
   - 源被 delete 的树产生 `W_SOURCE_DELETED` 警告，被跳过

2. **delete 语义**：
   - delete 树是独立根，不向上传播
   - 引用已 delete 的树的源 → 引用树操作跳过（warning），不报错
   - 祖先目录被 delete → 子路径源失效（warning），不报错

3. **分岔裁决**：
   - 多操作树 → `resolved_state="pending"` + `W_FOREST_BRANCHING`
   - 用户决策后 → `resolved_state="kept"` 或 `"deleted"`
   - 分支决策格式：`{root_path: source_path}` 向后兼容，增加 `"!"` / `""` 语义

4. **下游不改崩**：
   - `backup_ops` 零改动
   - `orchestrator` 仅字段更名
   - Web API 仅 key 变更

5. **全量测试通过**：
   - Python: 所有测试通过
   - 前端: Vitest + 构建通过

---

## 8. 第一次提交的合理范围

建议 **Step 1-3（引擎核心 + 测试）作为一个独立 PR**，在测试通过后再推进 Step 4-7（下游模块）。

引擎核心的工作量：约 3-4 小时（含测试）。
全栈（含前端）：约 6-8 小时。

---

## 9. 术语规范（重申）

| 中文 | 含义 | 代码中 |
|------|------|--------|
| **树** | ForestTree 实例 | `tree` |
| **根** | 树的根路径 | `root_path` |
| **结点** | 可视化图上的元素 | `node` |
| **分枝** | 多操作待决策 | `pending` / `branching` |
| **引用** | 树之间的依赖边 | `ref` / `refs` |
