# 审计报告后的疑问汇总

> 来源：`user_memo/audit_logs/2026-05-14_Architecture-Design-Freeze-and-Cleanup.md`
> 背景：审计报告在本次讨论中途落地，引入了一些与我们正在进行的修改不完全同步的规定

---

## 一、workspace 结构字段命名：camelCase vs snake_case

审计规定 localStorage 的 `modmanager:workspace` 使用 camelCase：

```json
{
  "managedEntries": {...},     // 审计要求
  "branchDecisions": {...},    // 审计要求
  "lastComputeSummary": {...}, // 审计要求
  "selectedRulePaths": [...]   // 审计要求
}
```

我们当前实现混用：
- `forestStore.branchDecisions`（camelCase ✅）
- 写入 localStorage 时用 `branch_decisions`（snakeCase ❌）
- `managed_entries`（snakeCase ❌）
- `results`（不是 `lastComputeSummary` ❌）

**疑问**：是否全面统一为审计规定的 camelCase？前端 Pinia store 和 localStorage key 都要改？

---

## 二、`useWorkspaceStore` —— localStorage 唯一写者

审计规定：
> Pinia 中的 `useWorkspaceStore` 是 localStorage 的唯一写者，所有页面通过 store action 修改决策，由 store 负责 flush

当前实现：各页面直接 `pers.save('workspace', ...)` 和 `pers.load('workspace')`。没有独立的 workspace store（`src/stores/` 下只有 `datasource.ts` 和 `forest.ts`）。

**疑问**：
- 是否立即创建 `src/stores/workspace.ts`？
- 它与现有的 `pers`（persistence.ts）是什么关系？workspace store 内部用 pers，还是替代 pers？
- 审计另外提到 `useComputeStore`（用于 aggregatedRuleSet 内存传递）——也需要新建吗？

---

## 三、`selectedRulePaths` vs `aggregatedRuleSet`

审计规定：
> `aggregatedRuleSet` 不进 localStorage（派生数据，体积大，可从 `selectedRulePaths` 重聚合）

我们当前实现：`aggregatedRuleSet` 存在 Pinia `forestStore` 里（内存），不写 localStorage——**这点已对齐**。

但审计要求存 `selectedRulePaths`（规则文件路径列表）到 localStorage，然后运行时重聚合。我们当前的 RulesOverviewPage 在聚合后存了 `aggregatedRuleSet` 到 Pinia，但没有存 `selectedRulePaths` 到 workspace。

**疑问**：
- 如果 localStorage 只存路径（不存聚合结果），RulesOverviewPage 聚合后的结果在页面刷新后丢失，需要重新聚合——这符合审计意图吗？
- `selectedRulePaths` 应该从 RulesOverviewPage 的 checkbox 选择中提取（用户勾选了哪些 `.kmmrule.json` 文件），还是从 user_config.rule_sources 中提取？
- hash 校验（`aggregatedRuleHash`）是否仍然需要？

---

## 四、`uiState` 并入 workspace

审计规定：
```json
{
  "uiState": {
    "sidebarCollapsed": false,
    "activeTab": "datasource",
    "libraryVisibility": {},
    "gameVisibility": {}
  }
}
```

当前实现：UI 状态分散在多个 persistence key（`datasource-libraryVisibility`、`datasource-gameVisibility` 等）。

**疑问**：
- 是否将 UI 状态全部迁移进 `workspace.uiState`？
- 如果迁移，`workspace` key 的读写频率增加（每次切换 tab、折叠 sidebar 都写 localStorage）——是否有性能顾虑？

---

## 五、Pipeline 端点为 EVOLVING

审计规定：
> `POST /api/pipeline/compute`、`/backup`、`/apply`、`/run` 是 EVOLVING（条件冻结），因为 GUI 流程还在设计

我们刚对 compute 做了重大修改（删 `aggregated_rule_path`，只接受 `aggregated_rule_set` dict，删 `working_pathstyle`）。

**疑问**：
- 这些修改是否应该视为"EVOLVING 范围内的正常迭代"，不构成破坏冻结？
- compute 端点现在是否还应该接受 `kmm_rule_paths`作为 fallback（审计没有明确禁止），还是已经完全移除？

---

## 六、文档清理残留

审计 §2.1 要求删除旧术语，以下未完成：

| 文档 | 残留 | 行号 |
|------|------|------|
| `DESIGN_STORAGE.md` | D4 决策："【已废弃。managed 决策迁移至前端 localStorage】" | 320 |
| `DESIGN_FOREST_MODEL.md` | 多处 "forest→trees" 迁移说明 | 196,249,267,297,322,323,327 |
| `DESIGN_RULE_AGGREGATOR.md` | nwname "已废弃 2026-04-30" | 169 |
| `DESIGN_REST_API.md` | 待查首段的 "forest→trees" migration note | 首段 |
| `DESIGN_REST_API.md` | status 应为 partially-stable | header |

**疑问**：
- `DESIGN_FOREST_MODEL.md` 的 "forest→trees" 迁移说明是否真的应该全部删除？这些是代码变更记录，删了会不会丢失历史上下文？
- 还是只删首段那个显著的 migration note，保留代码变更对照表？

---

## 七、`TERMS_FIELD_FREEZE.md` 新增 4 字段

审计要求新增冻结字段：
- `selectedRulePaths`
- `managedEntries`
- `branchDecisions`
- `lastComputeSummary`

当前 `TERMS_FIELD_FREEZE.md` 中"已废弃"节已删，但新字段未添加。

**疑问**：
- 这些字段的格式定义以审计报告为准，还是需要额外讨论？
- 审计中的 `managedEntries` 格式与我们设计的完全一致（`{ game: {appid: [path]}, mod: {mixed_id: [path]} }`）——是否可以确认冻结？

---

## 八、`DESIGN_REST_API.md` status 变更

审计要求 REST_API 状态从 `stable` 改为 `partially-stable`，因为 pipeline 端点未冻结。

**疑问**：
- 数据库、config、rules、backups 端点已经 STABLE——这些部分 status 写什么？
- 如何在同一个文档中表达"部分端点 stable、部分 evolving"？

---

## 九、前端 Transport Abstraction

审计规定：
> `src/api/transport.ts` — 接口定义（`invoke<T>(path, payload)`, `onProgress` callback）
> Tauri 时仅改此层的实现，组件零改动

当前没有 `transport.ts`。所有组件直接 `import { apiPost } from '../api/client'`。

**疑问**：
- 是否需要立即创建 `transport.ts` 抽象层？还是 Tauri 迁移时再做？
- 如果现在创建，`apiPost` 和 `streamSse` 都应通过 transport 接口调用吗？

---

## 十、审计是否会与后续 work_memo 讨论产生不一致

本次审计独立于我们的 `work_memo/2026-05-14_decisions.md` 裁定记录。两份文档之间可能有未对齐的决策。

**疑问**：
- 审计的"冻结"与我们裁定中的"方案 B"是否存在冲突（如 workspace 结构命名）？
- 是否需要将审计要求写入裁定记录，还是保持两份文档独立？
