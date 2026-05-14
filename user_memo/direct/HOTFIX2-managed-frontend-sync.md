# HOTFIX-2: managed 保存后前端本地状态不同步

> 状态: 已实现
> 关联: `HOTFIX-path-trailing-slash-and-managed.md`（已修复后端 managed 丢失问题，但前端口子未闭合）
> 目标文件: `frontend/src/stores/datasource.ts` + `frontend/src/pages/DataSourcePage.vue`

---

## 一、根因

`doSave()` 在 `POST /database/save` 成功后，**没有更新 datasource store 的 `lastResult`、`games`、`mods`**。导致：

1. `store.lastResult` 仍然是扫描时的原始数据（`managed` 全为 `false`）
2. `store.games[i].managed` 和 `store.mods[i].managed` 仍是 `false`
3. 页面重进时 `loadFromCache()` 从 localStorage 恢复旧数据 → `initLocalManaged()` 读取到的 managed 全为 `false` → UI 上 radio 全部未选中

虽然后端文件已正确保存了 managed 值，但前端从未把保存后的数据同步回自己的 store。

### 完整数据流断点

```
doSave() 成功路径:
  db = clone(lastResult)         ← managed 全 false
  db.game[i].managed = true      ← 写入用户选择
  POST /database/save → 文件写入 ✅
  forestStore.storedDatabase=db  ✅ (Forest 页面能用)
  ← 缺少: store.lastResult = db
  ← 缺少: store._populateFromDatabase(db)
```

---

## 二、修复方案

### 2.1 datasource store 新增公开方法

在 `frontend/src/stores/datasource.ts` 中新增一个公开方法 `updateDatabase`，调用私有的 `_populateFromDatabase` 并更新 `lastResult`：

```typescript
function updateDatabase(db: Record<string, unknown>) {
  lastResult.value = db
  _populateFromDatabase(db)
}
```

并在 return 块中导出。

### 2.2 DataSourcePage.vue 中 `doSave` 成功后调用

在 `doSave` 的成功分支中（第 411-424 行），`forestStore.dbManualOverride = false` 之后，新增：

```typescript
// Update datasource store so managed values are reflected in local state
store.updateDatabase(db)
```

---

## 三、改动范围

| 文件 | 函数/位置 | 修改内容 |
|------|----------|---------|
| `datasource.ts` | 新增 `updateDatabase` | 公开方法，调用 `_populateFromDatabase` + 更新 `lastResult` |
| `datasource.ts` | `return` 块 | 导出 `updateDatabase` |
| `DataSourcePage.vue` | `doSave` 成功分支 (~416行) | 添加 `store.updateDatabase(db)` |

**仅修改两个文件**，不涉及后端。

## 四、验证要点

1. 扫描完成后，勾选某个 game 的 radio → 点"保存当前选择" → 刷新页面（或从其他页面切回）→ radio 仍显示选中
2. 勾选后点"确认并进入规则概览" → 切回 DataSource 页面 → radio 选中状态保持
3. 未勾选的条目 managed 仍为 false
