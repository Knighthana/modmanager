# Phase 5 — localStorage 聚合 + compute 仅接受 dict

> Status: plan
> Authority: arch
> Source: `work_memo/2026-05-14_decisions.md` §十二

---

## Task 5.1: 后端 — 删除 compute/run 的路径参数

### 5.1.1 `schemas.py`
- `ComputeRequest`：删 `aggregated_rule_path`、`kmm_rule_paths`。保留 `aggregated_rule_set: dict | None = None`
- `RunRequest`：同上

### 5.1.2 `routes/pipeline.py`
- `/compute`：删 pre-check 中的路径判断。删 `resolved_agg_path` 和 `rule_paths` 的解析逻辑。直接传 `aggregated_rule_set=req.aggregated_rule_set`
- `/run`：同上

### 5.1.3 `orchestrator.py`
- `compute()` / `run()`：删 `aggregated_rule_path` 和 `kmm_rule_paths` 参数
- 内部删文件加载逻辑。`aggregated_rule_set` dict 直接使用

---

## Task 5.2: 前端 — localStorage 聚合为 `modmanager:workspace`

### 5.2.1 所有涉及 localStorage 的文件

全局搜索并替换以下分散 key → 统一读写：

**旧（分散）**：
```
pers.save('lastDatabase', ...)       pers.load('lastDatabase')
pers.save('decisions:...', ...)      pers.load('decisions:...')
pers.save('results:...', ...)        pers.load('results:...')
pers.save('aggregatedRuleSet', ...)  pers.load('aggregatedRuleSet')
```

**新（聚合）**：
```ts
// 读
const ws = pers.load<WorkspaceData>('workspace') || {}
// 写
pers.save('workspace', { ...ws, lastDatabase: 'default', perDatabase: {...}, aggregatedRuleSet: {...} })
```

### 5.2.2 `utils/persistence.ts`
- 注释更新：key 列表中 `modmanager:workspace` 替代分散 key

### 5.2.3 `DESIGN_GUI_WORKSPACE.md` 对应的 WorkspaceData 类型
```ts
interface WorkspaceData {
  lastDatabase: string
  perDatabase: Record<string, {
    decisions: { managed_entries?: Record<string, unknown>; branch_decisions?: Record<string, string> }
    results: { trees_count: number; mapping_count: number; warnings: string[]; errors: string[]; stats: Record<string, unknown>; inputs_hash: string; timestamp: string } | null
  }>
  aggregatedRuleSet: Record<string, unknown> | null
  aggregatedRuleHash: string
}
```

### 5.2.4 涉及的文件
- `frontend/src/pages/DataSourcePage.vue`
- `frontend/src/pages/ForestPage.vue`
- `frontend/src/pages/ComputePrepPage.vue`
- `frontend/src/pages/OperationsPage.vue`
- `frontend/src/pages/AdvancedPage.vue`
- `frontend/src/pages/RulesOverviewPage.vue`
- `frontend/src/components/DatabaseSelector.vue`
- `frontend/src/utils/persistence.ts`

---

## 执行顺序

1. Task 5.1.1 — schemas.py
2. Task 5.1.3 — orchestrator.py（先改签名，再改实现）
3. Task 5.1.2 — routes/pipeline.py
4. Task 5.2 — 前端 localStorage 聚合

---

## 验收

```bash
python -m pytest tests/ -x -q   # 全绿
cd frontend && npm run build     # 构建成功
```
