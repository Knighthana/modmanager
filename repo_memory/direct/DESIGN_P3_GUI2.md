# P3-GUI2：M4 交互增强 — 设计文档

创建：2026-05-06
状态：设计完成，待实现
来源：`work_memo/TODO.md` P3-GUI2

---

## 0. 现有能力盘点

| 能力 | 状态 |
|------|------|
| zoom/pan（滚轮缩放 + 拖拽平移）| ✅ |
| pending 树点击跳转 ConflictsPage | ✅ |
| 冲突裁决（ConflictsPage 表格单选）| ✅ |
| SVG 结点属性：`data-tree-node`、`data-tree-pending` | ✅ |
| 引用边渲染（虚线）| ✅ |
| `resolved_state` 着色（pending→红、deleted→灰等）| ✅ |

---

## 1. 新增功能

### 1.1 hover 整链高亮

**行为**：鼠标悬停在一棵树（含结点 + 边）上时，高亮：
- 该树本身
- 该树引用的所有树（`refs`）
- 引用该树的所有树（`referenced_by`）

其他树变暗（opacity 降低）。

**实现方案**：

#### 后端（forest_visual.py）

在 SVG 结点的 `<g>` 元素上新增两个属性：
- `data-tree-refs`：逗号分隔的被引用根路径列表（来自 `tree.refs`）
- `data-tree-referenced-by`：逗号分隔的引用者根路径列表（需反向索引计算）

改动位置：`_enrich_svg_nodes()` 函数。在已有 `data-tree-node` / `data-tree-pending` 设置处追加。

```python
# _enrich_svg_nodes() 中新增：
# 构建反向引用索引
referenced_by: dict[str, list[str]] = {}
for tree_node in model.nodes.values():
    for ref in tree_node.refs:
        referenced_by.setdefault(ref, []).append(tree_node.root_path)

# 设置属性时追加：
g_el.set("data-tree-refs", ",".join(node_obj.refs))
g_el.set("data-tree-referenced-by", ",".join(referenced_by.get(path, [])))
```

#### 前端（ForestViewer.vue）

在 `v-html` 渲染后，通过事件委托处理 hover：

```typescript
function onMouseOver(e: MouseEvent) {
    const target = e.target as HTMLElement
    const nodeEl = target.closest('[data-tree-node]') as HTMLElement | null
    if (!nodeEl) return
    
    const rootPath = nodeEl.getAttribute('data-tree-node')!
    const refs = (nodeEl.getAttribute('data-tree-refs') || '').split(',').filter(Boolean)
    const refby = (nodeEl.getAttribute('data-tree-referenced-by') || '').split(',').filter(Boolean)
    
    const highlightPaths = new Set([rootPath, ...refs, ...refby])
    
    // 所有节点变暗
    document.querySelectorAll('[data-tree-node]').forEach(el => {
        (el as HTMLElement).style.opacity = '0.2'
    })
    // 高亮相关节点
    highlightPaths.forEach(p => {
        const el = document.querySelector(`[data-tree-node="${CSS.escape(p)}"]`)
        if (el) (el as HTMLElement).style.opacity = '1'
    })
}

function onMouseOut() {
    document.querySelectorAll('[data-tree-node]').forEach(el => {
        (el as HTMLElement).style.opacity = '1'
    })
}
```

或在模板中添加事件监听：
```html
<div class="forest-container" @mouseover="onMouseOver" @mouseout="onMouseOut">
```

### 1.2 分叉超链接（已完成，仅验证）

当前 `ForestViewer.vue` 的 `onNodeClick` 已实现：pending 树点击 → `router.push({ name: 'conflicts', query: { root_path } })`。

需要验证 `ConflictsPage.vue` 是否接收 `root_path` query 参数并滚动/高亮对应行。若未实现，补充：
```typescript
// ConflictsPage.vue setup 中
const route = useRoute()
const highlightRootPath = ref(route.query.root_path as string || '')
```

### 1.3 拖拽选枝

**行为**：在 Forest 图中，对于 `resolved_state="pending"` 的树（红色分枝树），用户可以将它的一个源候选结点**拖拽到该 pending 树上**，表示选择该候选作为本树的决策。也可以直接**点击候选源结点**（在 pending 树被选中后）。

**实现方案（两阶段）**：

#### 阶段 A：点击候选快速选枝（优先实现）

1. 点击 pending 树 → 该树进入"选中"状态（蓝色边框高亮）
2. 选中状态下，所有通向该树的边变为高亮可点击
3. 点击高亮边或源结点 → 调用 `store.setDecision(root_path, source_path)`
4. 自动触发重新计算可视化

**改动**：
- `ForestViewer.vue`：新增 `selectedTree` ref，点击 pending 树时设置；点击边时执行决策
- `stores/forest.ts`：`setDecision` 已存在，无需改
- 后端 SVG：边的 `<path>` 元素需携带 `data-edge-source` / `data-edge-target` / `data-edge-action` 属性

#### 阶段 B：真正拖拽（后续可选）

- 源结点标记 `draggable="true"`
- pending 树标记为 drop zone
- dragstart → 记录源路径
- drop → `setDecision(pending_root, dragged_source)`

---

## 2. 后端改动（forest_visual.py）

### 2.1 `_enrich_svg_nodes()` 扩展

```python
def _enrich_svg_nodes(svg_text: str, model: GraphModel) -> str:
    # ... 现有逻辑 ...
    
    # 构建反向引用索引
    referenced_by: dict[str, list[str]] = {}
    for tree_node in model.nodes.values():
        for ref in tree_node.refs:
            if ref:  # ref 可能为空
                referenced_by.setdefault(ref, []).append(tree_node.root_path)
    
    for g_el in ...:
        # ... 现有 data-tree-node / data-tree-pending / title / desc 设置 ...
        
        # 新增：refs 和 referenced_by
        if node_obj and node_obj.refs:
            g_el.set("data-tree-refs", ",".join(node_obj.refs))
        if node_obj:
            rb = referenced_by.get(path, [])
            if rb:
                g_el.set("data-tree-referenced-by", ",".join(rb))
```

### 2.2 边的交互属性

DOT 生成的 SVG 中，边的 `<g class="edge">` 元素需要携带交互属性。但 Graphviz 生成的 SVG 结构不可控。

**替代方案**：在 `_render_html()` 的 JavaScript 部分（已有 svg pan/zoom JavaScript），边已经是手动绘制的 `<path>` 元素。修改 JS 使其为每条边设置 `data-edge-source` 和 `data-edge-target`：

```javascript
// 现有代码 already creates edges
for (const edge of graph.edges) {
    const path = el("path", {
        d: ...,
        stroke: ...,
        "data-edge-source": edge.source,
        "data-edge-target": edge.target,
        "data-edge-action": edge.action,
    });
}
```

注意：当前 `GraphModel.edges` 已包含 `source_path`, `target_path`, `action` 字段。

---

## 3. 前端改动（ForestViewer.vue）

### 3.1 模板层新增

```vue
<template>
  <el-card shadow="never" v-loading="store.isRunning">
    <!-- 提示条 -->
    <el-alert
      v-if="hoveredTree"
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 8px;"
    >
      <span>📍 {{ hoveredTree }}</span>
      <span v-if="hoveredRefs.length"> → 引用: {{ hoveredRefs.join(', ') }}</span>
    </el-alert>

    <div class="forest-container" @mouseover="onMouseOver" @mouseout="onMouseOut" @click="onNodeClick">
      <!-- 现有 SVG 渲染 -->
    </div>
  </el-card>
</template>
```

### 3.2 逻辑层新增

```typescript
// 选中状态（点击 pending 树后进入选择模式）
const selectedTree = ref<string | null>(null)
const hoveredTree = ref<string | null>(null)
const hoveredRefs = ref<string[]>([])

function onMouseOver(e: MouseEvent) {
    const target = e.target as HTMLElement
    const nodeEl = target.closest('[data-tree-node]') as HTMLElement | null
    if (!nodeEl) {
        // 检查是否hover在边上
        const edgeEl = target.closest('[data-edge-source]')
        if (edgeEl && selectedTree.value) {
            // hover在边上且处于选枝模式 → 高亮该边
        }
        return
    }
    
    const rootPath = nodeEl.getAttribute('data-tree-node')!
    const refs = (nodeEl.getAttribute('data-tree-refs') || '').split(',').filter(Boolean)
    const refby = (nodeEl.getAttribute('data-tree-referenced-by') || '').split(',').filter(Boolean)
    
    hoveredTree.value = rootPath
    hoveredRefs.value = refs
    
    const highlightPaths = new Set([rootPath, ...refs, ...refby])
    applyHighlight(highlightPaths)
}

function applyHighlight(paths: Set<string>) {
    document.querySelectorAll('[data-tree-node]').forEach(el => {
        (el as HTMLElement).style.opacity = '0.15'
    })
    document.querySelectorAll('[data-edge-source]').forEach(el => {
        (el as HTMLElement).style.opacity = '0.1'
    })
    paths.forEach(p => {
        const node = document.querySelector(`[data-tree-node="${CSS.escape(p)}"]`)
        if (node) (node as HTMLElement).style.opacity = '1'
    })
    // 高亮相关边
    paths.forEach(p => {
        document.querySelectorAll(`[data-edge-source="${CSS.escape(p)}"], [data-edge-target="${CSS.escape(p)}"]`)
            .forEach(el => { (el as HTMLElement).style.opacity = '1' })
    })
}

function onMouseOut() {
    hoveredTree.value = null
    document.querySelectorAll('[data-tree-node], [data-edge-source]').forEach(el => {
        (el as HTMLElement).style.opacity = '1'
    })
}

function onNodeClick(e: MouseEvent) {
    if (isDragging.value) return
    const target = e.target as HTMLElement
    
    // 检查是否点击边
    const edgeEl = target.closest('[data-edge-source]') as HTMLElement | null
    if (edgeEl && selectedTree.value) {
        const edgeTarget = edgeEl.getAttribute('data-edge-target')!
        const edgeSource = edgeEl.getAttribute('data-edge-source')!
        if (edgeTarget === selectedTree.value) {
            // 选枝：将 source 作为决策
            store.setDecision(selectedTree.value, edgeSource)
            selectedTree.value = null
            // 触发重新可视化
            return
        }
    }
    
    // 检查是否点击结点
    const nodeEl = target.closest('[data-tree-node]') as HTMLElement | null
    if (!nodeEl) return
    
    const rootPath = nodeEl.getAttribute('data-tree-node')!
    const isPending = nodeEl.hasAttribute('data-tree-pending')
    
    if (isPending) {
        if (selectedTree.value === rootPath) {
            // 再次点击取消选中
            selectedTree.value = null
        } else {
            // 进入选枝模式
            selectedTree.value = rootPath
        }
    }
}
```

### 3.3 CSS 增强

```css
[data-tree-node] {
    transition: opacity 0.2s ease;
}

[data-edge-source] {
    transition: opacity 0.2s ease;
}

[data-tree-node][data-tree-pending="true"] {
    cursor: pointer;
}

[data-tree-node].selected {
    filter: drop-shadow(0 0 6px #3b82f6);
    stroke: #3b82f6;
}
```

---

## 4. 测试策略

| # | 测试 | 说明 |
|---|------|------|
| T1 | `test_svg_has_refs_attribute` | 验证 SVG 结点有 `data-tree-refs` 属性 |
| T2 | `test_svg_has_referenced_by` | 验证 SVG 结点有 `data-tree-referenced-by` 属性 |
| T3 | `test_hover_highlight_dims_others` | 前端：hover 结点时其他结点变暗 |
| T4 | `test_hover_highlight_refs` | 前端：hover 时引用链高亮 |
| T5 | `test_click_pending_selects_tree` | 前端：点击 pending 树进入选枝模式 |
| T6 | `test_click_edge_sets_decision` | 前端：选枝模式下点击边产生决策 |

---

## 5. 任务分解

```
Task GUI2-01: forest_visual.py — SVG 结点 data-tree-refs/data-tree-referenced-by 属性
Task GUI2-02: forest_visual.py — 测试更新
Task GUI2-03: ForestViewer.vue — hover 整链高亮逻辑
Task GUI2-04: ForestViewer.vue — 点击选枝交互
Task GUI2-05: frontend — Vitest 测试更新
Task GUI2-06: 全量回归（Python + 前端）
```

---

## 6. 验收标准

1. 鼠标悬停任一棵树 → 该树 + 其引用链 + 被引用链高亮，其余变暗
2. 鼠标移出 → 全部恢复
3. 点击 pending 树 → 进入选枝模式（蓝色高亮边框）
4. 选枝模式下点击通向该树的边 → 产生决策，自动刷新可视化
5. 全量测试通过（Python + 前端 Vitest + 构建）
