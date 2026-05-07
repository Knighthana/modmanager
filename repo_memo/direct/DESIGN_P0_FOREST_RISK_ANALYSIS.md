# P0：森林模型重构 — 风险排查与架构分析

创建：2026-05-06
状态：分析阶段（待决策）
来源：`work_memo/TODO.md` P0 + `work_memo/FOREST_DELETE_FORK_DESIGN.md`
前置审查：全部核心源码（engine.py 537行 / orchestrator.py 334行 / forest_visual.py 846行）

---

## 1. 现状剖析：当前 `compute_mapping` 的数据流

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
    │  4. 输出 forest (扁平列表)   │
    │     + final_mapping          │
    └──────────────┬───────────────┘
                   │
    { warnings, errors, forest, final_mapping }
```

### 1.1 当前 forest 数据结构

```python
# forest[i] = {
#     "path":              str,      # 目标文件绝对路径
#     "destin_mixed_id":   str,      # 所属 mod 的 mixed_id
#     "changerequest":     [dict],   # 有序的源请求列表
#     "warning":           str|None, # "W_FOREST_BRANCHING" 或 None
#     "candidates":        [str],    # 分岔候选源列表
# }
```

**关键特征**：
- forest 是**扁平列表**，不是图；每个条目是一个"目标文件"
- "分岔"（branching）发生在一个目标有多条 changerequest 时
- changerequest 的 `path` 字段是源文件路径；若该路径恰好也是另一个目标 → 形成链
- 链的解析通过 `_resolve_effective_leaf_request` **自上而下**递归跟踪

### 1.2 当前 delete 的处理路径

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

### 1.3 `_resolve_effective_leaf_request` 的递归逻辑

```python
# engine.py L114-149
def _resolve_effective_leaf_request(target, mapping, branch_decisions, errors, visiting):
    # 1. 对当前 target 的 changerequests 进行分岔裁决
    chosen = _pick_request_by_action_order(...)  # 或分支决策

    # 2. chosen.path 是源路径
    src_path = chosen.get("path", "")

    # 3. 若 src_path 也是 mapping 中的某个目标 → 递归向下追踪
    if src_path in mapping:
        resolved = _resolve_effective_leaf_request(src_path, ...)
        return resolved  # 向下传递 delete 语义 ← 问题所在

    return chosen
```

**关键观察**：递归是**自顶向下**的（从最终目标追踪到根源），delete 语义在此向**上**传递给更外层的调用者。

---

## 2. 新模型的设计要点（来自 FOREST_DELETE_FORK_DESIGN.md）

### 2.1 核心思想：独立根 + 引用

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

### 2.2 数据结构：ForestTree

```python
@dataclass
class ForestTree:
    root_path: str                  # 树的根路径（一个文件）
    operations: list[ChangeRequest] # 对这棵树根的操作列表
    refs: list[str]                 # 引用了哪些其他树的根
    resolved: bool                  # 是否已解析
    resolved_state: str | None      # "deleted" | "kept" | None
```

### 2.3 解析算法：从底向上

```
拓扑排序（被引用者先于引用者）→ 从底向上逐层解析：
  Step 1: 查询所有被引用树的状态
  Step 2: 若有自己的操作 + 源均可用 → 用户在此决策
  Step 3: 标记为已解析
```

### 2.4 用户决策的粒度变化

| 维度 | 旧模型 | 新模型 |
|------|--------|--------|
| 决策单位 | 每个**目标路径** | 每棵**树**（根路径） |
| `branch_decisions` 格式 | `{target: chosen_source}` | `{tree_root_path: decision}` |
| 决策内容 | 选哪个源 | 对这棵树执行什么操作 |

---

## 3. 关键架构判断：重构 vs 修改

### 3.1 判断矩阵

| 维度 | 纯重构（内部不变） | 新模型（公开接口变） |
|------|-------------------|---------------------|
| `compute_mapping` 内部逻辑 | 小改 | **大改**（解析算法重写） |
| 输出 `forest` 结构 | 不变 | 可能增加字段 |
| 输出 `final_mapping` 结构 | 不变 | 结构不变，语义可能变 |
| `branch_decisions` 输入 | 不变 | **格式改变** |
| 下游 orchestrator | 不变 | 可能需要适配 |
| 下游 forest_visual.py | 不变 | **大幅修改**（概念从 target 变为 tree） |
| Web API schemas | 不变 | 可能需要适配 |
| 前端 TypeScript 类型 | 不变 | 可能需要适配 |
| 前端 ForestViewer/ConflictsPage | 不变 | **大改**（冲突裁决模型改变） |

### 3.2 结论：这是一个 **模型演进**，不是纯重构

`compute_mapping` 的输出格式、`branch_decisions` 的语义、以及前端交互模型全部需要变化。这不是可以"内部重构、外部不变"的改动。

---

## 4. 爆炸半径分析

### 4.1 直接代码改动（按模块）

| 模块 | 文件 | 改动量评估 | 风险等级 |
|------|------|-----------|---------|
| **引擎核心** | `engine.py` | **重写** `_resolve_effective_leaf_request` 及相关逻辑（约150行）；新增 `ForestTree` 构建 + 解析算法（约200+行） | 🔴 高 |
| **引擎核心** | `paths.py` | 可能无改动（root path 确定逻辑不变） | 🟢 低 |
| **引擎核心** | `validation.py` | 无改动（输入校验不变） | 🟢 低 |
| **编排层** | `orchestrator.py` | 小改（`PipelineResult` 可能增加字段） | 🟡 中 |
| **可视化** | `forest_visual.py` | **重写** `_build_graph_model`（tree 概念替换 target）；新增 ref 边渲染 | 🔴 高 |
| **Web API** | `schemas.py` | `branch_decisions` schema 格式变更 | 🟡 中 |
| **Web API** | `adapters.py` | 适配新的 `PipelineResult` 字段 | 🟡 中 |
| **Web API** | `routes/pipeline.py` | `visualize` 端点输入可能变化 | 🟡 中 |
| **前端** | `types/index.ts` | `ConflictItem` / `branch_decisions` 类型变更 | 🟡 中 |
| **前端** | `stores/forest.ts` | 状态管理和冲突裁决逻辑重写 | 🔴 高 |
| **前端** | `pages/ConflictsPage.vue` | 冲突展示改为"按树裁决" | 🔴 高 |
| **前端** | `components/ForestViewer.vue` | 树引用关系的渲染和交互 | 🔴 高 |

### 4.2 测试改动

| 测试文件 | 行数 | 受影响测试数（估算） | 说明 |
|----------|------|---------------------|------|
| `test_engine.py` | 759 | **~20** | 核心引擎测试，涉及 delete 传播、分岔裁决 |
| `test_contract.py` | 321 | **~5** | 输出契约验证（forest/final_mapping 格式） |
| `test_integration_fixtures.py` | 786 | **~10** | 集成测试场景（F004 成环、F006 分岔、F007 裁决） |
| `test_forest_visual.py` | 229 | **~8** | 可视化测试，森林模型变化 |
| `test_orchestrator.py` | 139 | **~3** | 编排层测试 |
| `test_web_api.py` | 463 | **~5** | Web API 测试 |
| **合计** | **~2697** | **~51** | |

当前全量：280 tests 通过。预估改写/新增约 51 个测试用例。

### 4.3 前端测试

前端的 Vitest 14 个测试中，与 forest store、冲突裁决相关的测试需要更新（估计 ~5-8 个）。

---

## 5. 风险清单

### 🔴 高风险

| # | 风险 | 描述 | 缓解措施 |
|---|------|------|---------|
| R1 | **delete 语义兼容性** | 新模型下 delete 不再"刨根移栽"，现有依赖此行为的规则可能行为改变 | 在 P0 文档中明确定义新旧 delete 语义差异，审查现有测试中的 delete 场景 |
| R2 | **前端冲突裁决大改** | 从"按目标选源"变为"按树决策"，前端 ConflictsPage 和 ForestViewer 需重写交互逻辑 | 前后端同步设计，先定接口契约再分别实现 |
| R3 | **branch_decisions 格式断裂** | `{target: chosen_source}` → `{tree_root: decision}`，新旧格式不兼容 | 使用不同的 key 命名/new endpoint 或版本化 |
| R4 | **forest_visual 渲染** | 当前可视化以"target 结点"为中心，新模型以"树"为中心，增 ref 边 | 重写 `_build_graph_model`，复用部分 DOT/SVG 生成逻辑 |

### 🟡 中风险

| # | 风险 | 描述 | 缓解措施 |
|---|------|------|---------|
| R5 | **拓扑排序正确性** | 树间引用可能形成复杂 DAG，拓扑排序和环检测必须正确 | 复用已有 `find_cycles()`；新增独立的树级拓扑排序函数 |
| R6 | **用户决策反馈到 final_mapping** | GAP 3 中尚未确定的：用户拒绝某棵树的 delete 后，引用者的状态如何传播 | 设计文档中详细定义决策→final_mapping 的状态机 |
| R7 | **ForestTree 构建逻辑** | GAP 1-2 中未确定的：如何从当前 mapping dict + edges dict 提取 ForestTree | 需要在 engine.py 的构建循环中增加一步提取逻辑 |

### 🟢 低风险

| # | 风险 | 描述 | 缓解措施 |
|---|------|------|---------|
| R8 | **同 mod 去重逻辑** | 当前 `later wins` 的去重是在 changerequest 粒度做的，新模型需确认是否要保持 | 同 mod 内的去重逻辑不变（before tree extraction） |
| R9 | **filefoldertree 过渡检查** | `_check_filefoldertree_transition` 是独立的，不受影响 | 零改动 |
| R10 | **acf_parser / vdf_parser** | 完全不相关 | 零改动 |

---

## 6. 决策点（需要用户确认）

### D1：模型改变的激进程度

**方案 A（稳健）**：在 `compute_mapping` 内部建立 ForestTree 模型用于冲突裁决，但保持输出格式（`forest` + `final_mapping`）的向后兼容。

- 优点：前端和 Web API 零改动；改动集中在 engine.py
- 缺点：内部模型和外部模型不一致，维护两套数据结构；forest 可视化没有提升

**方案 B（中间）**：新模型同时产出两套输出——旧格式 `forest`（保证后端兼容）和新格式 `trees`（供前端消费）。前端逐步迁移到新格式。

- 优点：渐进式迁移，风险可控
- 缺点：过渡期内同时维护两套，最终要清理旧格式

**方案 C（激进）**：全栈同步切换到新模型，`forest` 格式改为 `trees` 格式，前端、Web API、可视化全部改。

- 优点：一次到位，没有技术债务
- 缺点：爆炸半径最大，多个模块同时改写，调试复杂

### D2：delete 语义的精确行为

新模型中，若某棵树的根被删除，引用它的树应如何处理？

- **行为 A**：引用者操作直接失败，报错并标记 `E_SOURCE_DELETED`
- **行为 B**：引用者操作跳过（warning），不报错，final_mapping 中不出现
- **行为 C**：给用户在引用树上选择"放弃此操作"或"改用其他源"

### D3：P0 的实现边界

FOREST_DELETE_FORK_DESIGN.md 中标记了尚未设计的 T5（目录 delete 裂变）和 T10（引用可视化前端交互）。P0 是否要涵盖这些？

---

## 7. 建议路径

基于风险分析，我建议采用 **方案 B（中间路线）**：

1. **第一阶段**：在 `engine.py` 内部构建 ForestTree + 自底向上解析算法，同时输出：
   - 旧格式 `forest`（保证后端兼容，删除 `W_DELETE_LEAF_PROMOTED`，改为新语义）
   - 新格式 `trees`（包含 tree_id、root_path、operations、refs、resolved_state）
2. **第二阶段**：更新 `forest_visual.py` 消费 `trees`
3. **第三阶段**：更新前端消费 `trees`
4. **第四阶段**（可选）：废弃 `forest` 旧格式

但实际上，用户说了"从 P0 开始"，而且项目目前处于可控状态。让我先向用户呈现分析结果，等待确认关键决策后再做详细方案设计。
