# 森林模型：独立根 + 引用

创建：2026-04-30
状态：设计草案（§1-5 已废弃，以 §7 起为准）
最后更新：2026-04-30 — 加入解析算法、成环/断头检测

---

## 历史草案（已废弃，仅供追溯）

<details>
<summary>§1-5: 旧 fork 模型（filenotexist / holdasoriginal）</summary>

### §1. 问题陈述

Author A: replace /modA/file.png → /game/target.png  
Author B: delete  /modA/file.png

缺陷：delete 语义在递归中从"删除源文件"变为"删除目标文件"。

### §2-5. 旧方案（已废弃）

fork 模型：filenotexist / holdasoriginal + 延迟删除队列。

**废弃原因**：刨根移栽导致 (a) delete 语义污染 (b) 原根位置空洞 (c) holdasoriginal 不给用户否决权 (d) 延迟删除可能误删 Phase 2 产出物。

</details>

---

## 7. 正式设计：独立根 + 引用

### 7.1 核心思想

每棵树的根是独立存在的。树之间通过**引用**（不是移植）表达依赖。树的根不被移植到另一棵树下方——只标记"此树引用彼树作为源"。

```
Forest（每棵树独立）:
  Tree C: /modC/other.png ──[delete]           ← 独立根
  Tree A: /modA/file.png ──[keep]               ← 独立根
              ↑ ref: /modC/other.png            ← 标记，非占有
  Tree B: /game/target.png                      ← 独立根
              ↑ ref: /modA/file.png             ← 标记，非占有
```

### 7.2 数据结构

```python
@dataclass
class ForestTree:
    root_path: str                  # 自己的根路径
    operations: list[ChangeRequest] # 自己挂的操作（聚合后的 actionlist）
    refs: list[str]                 # 引用了哪些其他树的根作为源
```

### 7.3 与旧模型的关键区别

| | 刨根移栽（旧，§1-5） | 独立根 + 引用（新） |
|---|---|---|
| delete 语义 | 随迁移污染 | 留在原地，不变 |
| 原根位置 | 空洞 | 独立存在，用户可在此决策 |
| 用户否决权 | 需额外机制（holdasoriginal） | 天然支持——每棵树自己决策 |
| delay-delete | 需要，且危险（Q5） | 不需要——每棵树独立执行 |
| 树的数量 | 少 | 多，但每棵树语义正确 |

### 7.4 全局约定

- `glob` 展开以**磁盘当前状态**为准，不模拟中间操作后的状态
- 同一 actionlist 内：`delete → create` 不产生 `W_CREATE_TARGET_EXISTS_OVERWRITE`（前序 delete 已清空）
- 同一 actionlist 内：`replace → delete` 无冲突（作者意图是先替换后删源）
- `rename_then_replace` 和 `clear_then_copy` 已废弃（commit `26e72c9`），不再讨论

---

## 8. 解析算法

### 8.1 原则：从底向上，逐层消除

被引用树的分岔先消除 → 向上传递布尔结论 → 引用树据此决定命运。

```
解析顺序: 丙（最底层，无人引用）→ 乙（引用丙）→ 甲（引用乙）

Step 1: 丙 → 用户决策 → 丙变为单一结点："文件已删除"或"文件保留"
Step 2: 乙 → 查询丙 → 源可用/不可用 → 乙执行/失败 → 乙变为单一结点
Step 3: 甲 → 查询乙 → 同上 → 甲变为单一结点
```

### 8.2 算法

```python
def resolve_forest(forest: list[ForestTree]) -> None:
    # 1. 拓扑排序（被引用者先于引用者）
    order = topological_sort_by_refs(forest)
    
    # 2. 从底向上逐层解析
    for tree in order:
        # 2a. 查询所有被引用树的状态
        for ref_path in tree.refs:
            ref_tree = find_tree_by_root(forest, ref_path)
            if ref_tree.resolved_state == "deleted":
                # 源不存在 → 依赖此源的操作全部失败
                tree.mark_failed(f"source deleted: {ref_path}")
        
        # 2b. 若树有自己的操作 + 源均可用 → 用户在此决策
        if tree.has_own_operations() and not tree.is_failed():
            decision = user_choose(tree)  # 冲突裁决 UI
            tree.apply_decision(decision)
        
        # 2c. 标记为已解析
        tree.resolved = True
```

### 8.3 用户决策内容

每棵树的分岔选项取决于它自己的操作类型。用户只能决策"对这棵树执行什么"，不能跨越树边界决策。

---

## 9. 成环与断头检测

### 9.1 成环检测

树间引用图是否成环。**复用已有 `find_cycles()` 算法**。

```python
# 构建树级边：root_path → 被引用的 root_path 集合
ref_graph = {t.root_path: set(t.refs) for t in forest}
cycles = find_cycles(ref_graph)
if cycles:
    errors.append(f"E_FOREST_CYCLE: {cycles}")
```

### 9.2 成环处理

| 方案 | 行为 |
|------|------|
| **A: 环内集体裁决** | 环内所有树合并为一个决策单元（默认） |
| **B: 打破环** | 用户指定环内某棵树的操作为"优先"，其余按拓扑处理 |

### 9.3 断头路检测

引用了一个不是森林根结点的路径。

```python
all_roots = {t.root_path for t in forest}
for tree in forest:
    for ref in tree.refs:
        if ref not in all_roots:
            errors.append(f"E_DANGLING_REF: {tree.root_path} references {ref}")
```

---

## 10. 分支决策跨树传递（T8 已解决）

用户决策的内容是"对这棵树的根文件做什么操作"。决策完成后，树变为单一结点，向外传递的唯一信息是**这条路径上的文件是否还存在**——一个布尔值。

- 文件存在 → 所有引用者可以正常使用它作为源
- 文件不存在 → 所有引用者的操作因源缺失而失败

传递粒度：**布尔信号**。不传递操作细节，不按引用者区分。

---

## 11. 特例 trick 枚举（更新）

`rename_then_replace` 和 `clear_then_copy` 已废弃，相关 trick 移除。

| # | Trick | 处理方式 |
|---|-------|---------|
| T1 | same actionlist: `delete X → create/replace X` | 不产生 overwrite 警告 |
| T2 | same actionlist: `replace X→T → delete X` | 无冲突，作者意图 |
| T3 | 跨树依赖解析 | 拓扑排序，从底向上查询被引用树状态 |
| T4 | 多树引用同一根 | 同 T3，共享布尔结论 |
| T5 | delete 是目录，源是目录内文件 | 目录 delete 裂变到子路径 |
| T8 | 分支决策跨树传递 | 布尔信号（文件存在/不存在）→ 已解决 |
| T9 | 执行顺序 | 被引用树先执行，引用树后执行（拓扑序） |
| T10 | 引用关系可视化 | Forest 图中用标签 + 点击跳转标注引用 |
| T11 | glob + 前序操作语义 | glob 以磁盘为准，不模拟中间状态 |

---

## 12. 待后续设计的问题

以下问题在逻辑上已闭环，但实现细节待展开：

- T5（目录 delete 裂变到子路径）的具体实现算法
- T10（引用可视化）的前端交互方案
- 拓扑排序的具体实现（是否需单独模块）

---

## 13. 与现有引擎的对接 GAP（设计空白，待填）

以下三个问题不在当前文档范围内，属于"如何把这个模型嵌入现有 `compute_mapping`"的实现细节：

| # | GAP | 说明 |
|---|-----|------|
| G1 | ForestTree 如何从 mapping dict 构建 | 现有 `compute_mapping` 产出 `{"forest": [...], "final_mapping": [...]}`。forest 是扁平结点列表，需要从中提取"根路径 + 操作 + 被引用的源"来构建 ForestTree 列表 |
| G2 | 引用的边如何从 changerequest 提取 | changerequest 中 `path` 是源文件路径。若该路径也是另一个 target，则形成引用边。提取逻辑需要在现有循环中追加一步 |
| G3 | 用户决策后如何反馈给 final_mapping | 用户在各树的冲突裁决中做了选择后，需要重新计算 final_mapping——让被拒绝的操作失败、被接受的操作正常产出映射条目 |

这三个 GAP 在当前设计文档范围内无法解答——需要阅读 `engine.py` 的完整 `compute_mapping` 函数并设计注入点。
